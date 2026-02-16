import math
import streamlit as st
from simcam_data import LENS_DATABASE, BALL_RADIUS_MM, BALL_DIAMETER_MM

# --- CALCULATION LOGIC ---
def get_sensor_diagonal_mm(sensor):
    w_mm = sensor['width_px'] * (sensor['pixel_size'] / 1000)
    h_mm = sensor['height_px'] * (sensor['pixel_size'] / 1000)
    return math.sqrt(w_mm**2 + h_mm**2)

def get_compatible_lenses(sensor, min_coverage_pct=100.0, include_varifocal=True):
    diag = get_sensor_diagonal_mm(sensor)
    threshold = diag * (min_coverage_pct / 100.0)
    
    filtered_lenses = []
    for l in LENS_DATABASE:
        if l[3] < threshold:
            continue
        is_vf_lens = l[4]
        if is_vf_lens and not include_varifocal:
            continue
        filtered_lenses.append(l)
    return filtered_lenses

def find_nearest(array, value):
    idx = (math.fabs(array[0] - value))
    near = array[0]
    for val in array:
        if math.fabs(val - value) < idx:
            idx = math.fabs(val - value)
            near = val
    return near

def golden_section_search(f, a, b, tol=1.0):
    """Minimizes f(x) over [a, b] using Golden Section Search."""
    gr = (math.sqrt(5) + 1) / 2
    c = b - (b - a) / gr
    d = a + (b - a) / gr
    while abs(b - a) > tol:
        if f(c) < f(d):
            b = d
            d = c
            c = b - (b - a) / gr
        else:
            a = c
            c = d
            d = a + (b - a) / gr
    return (b + a) / 2


def calculate_metrics(sensor, binning, wavelength, focal, f_stop, dist, 
                      include_club, num_pos, first_pos, spacing, focus_offset, 
                      coc_mult, cam_z_offset, fixed_y_center=None, ignore_ball_fit=False,
                      is_stereo=False, stereo_base=0, stereo_align="Horizontal"):
    
    bin_factor = 2 if binning else 1
    px_size_um = sensor["pixel_size"] * bin_factor
    px_size_mm = px_size_um / 1000.0
    width_px = sensor["width_px"] / bin_factor
    height_px = sensor["height_px"] / bin_factor
    sensor_w = width_px * px_size_mm
    sensor_h = height_px * px_size_mm
    
    raw_fov_w = (sensor_w * dist) / focal
    raw_fov_h = (sensor_h * dist) / focal
    
    if is_stereo:
        if stereo_align == "Horizontal":
            eff_fov_w = max(0, raw_fov_w - stereo_base)
            eff_fov_h = raw_fov_h
        else: # Vertical
            eff_fov_w = raw_fov_w
            eff_fov_h = max(0, raw_fov_h - stereo_base)
    else:
        eff_fov_w = raw_fov_w
        eff_fov_h = raw_fov_h
    
    if fixed_y_center is not None:
        fov_center = fixed_y_center
    else:
        if include_club:
            fov_bottom = -152.4
            fov_center = fov_bottom + (eff_fov_w / 2)
        else:
            fov_bottom = first_pos - 25.4
            fov_center = fov_bottom + (eff_fov_w / 2)
            
    fov_top = fov_center + (eff_fov_w / 2)
    fov_bottom = fov_center - (eff_fov_w / 2)
    
    base_cam_height = raw_fov_h / 2 
    total_cam_height = base_cam_height + cam_z_offset
    res = width_px / raw_fov_w
    
    focus_dist = dist + focus_offset
    if focus_dist <= 0: focus_dist = 1
    coc = px_size_mm * coc_mult 
    H = (focal**2) / (f_stop * coc) if f_stop > 0 else 0.001
    dn = (H * focus_dist) / (H + focus_dist)
    if H > focus_dist:
        df = (H * focus_dist) / (H - focus_dist)
        dof = df - dn
    else:
        df = 99999
        dof = 99999
    
    base_params = st.session_state.base_params
    base_px_area = base_params["sensor"]["pixel_size"] ** 2
    base_wavelength = base_params.get('wavelength', 810)
    base_qe = base_params["sensor"]["qe"].get(base_wavelength, base_params["sensor"]["qe"].get(810, 0.2))
    base_score = (base_qe * base_px_area) / ((base_params["aperture"]**2) * (base_params["distance"]**2))
    qe = sensor["qe"].get(wavelength, sensor["qe"].get(810, 0.2))
    current_score = (qe * (px_size_um**2)) / ((f_stop**2) * (dist**2))
    bright_pct = (current_score / base_score) * 100 if base_score > 0 else 0
    
    is_valid = True
    if not ignore_ball_fit:
        for i in range(num_pos):
            ball_center = first_pos + (i * spacing)
            if (ball_center - BALL_RADIUS_MM) < fov_bottom or (ball_center + BALL_RADIUS_MM) > fov_top:
                is_valid = False
                break
    
    safe_near = max(0, dist - dn)
    flight_dist = first_pos + (num_pos - 1) * spacing
    if flight_dist <= 0: flight_dist = 1
    
    min_h_angle = -math.degrees(math.atan(safe_near / flight_dist))
    if df > 99999:
         max_h_angle = 90.0
         safe_far = 9999
    else:
         safe_far = max(0, df - dist)
         max_h_angle = math.degrees(math.atan(safe_far / flight_dist))
    
    fov_h_at_near = (sensor_h * dn) / focal
    if is_stereo and stereo_align == "Vertical":
        fov_h_at_near = max(0, fov_h_at_near - stereo_base)
    fov_bottom_z_near = total_cam_height - (fov_h_at_near / 2)
    min_v_rad = math.atan((fov_bottom_z_near - 0) / flight_dist)
    min_v_angle = math.degrees(min_v_rad)
    
    if df > 50000:
        max_v_rad = math.radians(89.0)
        fov_top_z_far = 5000
    else:
        fov_h_at_far = (sensor_h * df) / focal
        if is_stereo and stereo_align == "Vertical":
            fov_h_at_far = max(0, fov_h_at_far - stereo_base)
        fov_top_z_far = total_cam_height + (fov_h_at_far / 2)
        max_v_rad = math.atan((fov_top_z_far - BALL_DIAMETER_MM) / flight_dist)
    max_v_angle = math.degrees(max_v_rad)

    if not is_valid and not ignore_ball_fit:
        min_h_angle = max_h_angle = min_v_angle = max_v_angle = None

    return {
        "res": res, "dof": dof, "fov_w": eff_fov_w, "fov_h": eff_fov_h,
        "raw_fov_w": raw_fov_w, "raw_fov_h": raw_fov_h,
        "bright": bright_pct, "px_size_mm": px_size_mm, "qe": qe,
        "near_limit": dn, "far_limit": df,
        "min_h_angle": min_h_angle, "max_h_angle": max_h_angle,
        "min_v_angle": min_v_angle, "max_v_angle": max_v_angle,
        "fov_bottom": fov_bottom, "fov_top": fov_top, "fov_center": fov_center,
        "total_cam_height": total_cam_height,
        "focus_dist": focus_dist,
        "safe_near_dev": safe_near, "safe_far_dev": safe_far,
        "flight_dist": flight_dist,
        "fov_bottom_z_near": fov_bottom_z_near, "fov_top_z_far": fov_top_z_far,
        "min_v_rad": min_v_rad, "max_v_rad": max_v_rad,
        "stereo_base": stereo_base if is_stereo else 0,
        "stereo_align": stereo_align if is_stereo else None
    }
