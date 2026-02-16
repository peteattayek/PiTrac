import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
from simcam_data import (
    DEFAULT_BASE_PARAMS, SENSORS, LENS_DATABASE, BALL_DIAMETER_MM, sensor_help_text
)
from simcam_calc import (
    get_compatible_lenses, find_nearest, golden_section_search, calculate_metrics
)
from simcam_plots import (
    plot_schematic, plot_sensor_view_final
)

# --- CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="SimCam Optics Calculator", layout="wide")

# Initialize Session State for Baseline
if 'base_params' not in st.session_state:
    st.session_state.base_params = DEFAULT_BASE_PARAMS.copy()

# --- UI SETUP ---
st.title("📷 SimCam Optics Calculator")

# --- HELP SECTION ---
with st.sidebar.expander("❓ How to Use this Calculator"):
    st.markdown("""
    ### **1. Sensor Config (Sidebar)**
    * **Sensor:** Select your camera sensor model.
    * **Binning:** Enable 2x2 binning to increase sensitivity (4x brightness) but halve resolution.
    * **Rotate Camera 90°:** Swaps width and height for portrait orientation.
    * **Wavelength:** Select the IR light wavelength (affects QE/Brightness).
    * **Stereoscopic:** Enable for dual-camera setups.
        * **Alignment:** Horizontal or Vertical relative to each other.
        * **Ratio:** 1:5 is standard. 1:30 offers more overlap but less depth precision.

    ### **2. Optimization Targets (Sidebar)**
    * **Min Resolution:** Minimum pixels per mm required on the ball.
    * **Min Brightness:** Minimum relative brightness vs baseline (100% = same as baseline).
    * **Min Distance:** Closest allowed distance from Camera to Tee (safety constraint).
    * **Min VLA:** Launch angle needed to see the floor (0 deg = Floor Visible).
    * **Circle of Confusion:** Tolerance for blur (Higher = larger focus zone, less sharp).

    ### **3. Ball Data (Sidebar)**
    * **Include Club Data:** Adds tracking lines for club head (4" before, 1" after tee).
    * **Number of Positions:** How many ball exposures are captured.
    * **First Image Position:** Distance from Tee to the *first* ball image.
    * **Position Spacing:** Distance between sequential ball images.

    ### **4. Main Window Controls**
    * **Optimize System:** Auto-finds the best lens & geometry to meet Targets.
    * **Manual Sliders:**
        * **Focal Length & Aperture:** Fine-tune lens specs.
        * **Distance Perpendicular:** Camera distance from the tee line (X-axis).
        * **Focus Offset:** Shift the focal plane to center the depth of field.
        * **Vert Cam Offset:** Adjust camera height to see the floor.
        * **Distance Parallel:** Shift camera left/right along the swing line.

    ### **5. Analyze the Plots**
    * **Top View:**
        * **Blue Zone:** The camera's Field of View (FOV).
        * **Green Box:** The sharp Focus Zone (Depth of Field).
        * **Red Circles:** Ghost balls showing Horizontal Launch Angle (HLA) limits.
    * **Camera View (YZ):**
        * **Orange Balls:** Max vertical launch angle that fits in the frame.
        * **Blue Lines:** Club tracking window (if enabled).
    """)

# Sidebar
st.sidebar.header("Sensor Config")
sensor_name = st.sidebar.selectbox("Select Sensor", list(SENSORS.keys()), help=sensor_help_text)
sensor = SENSORS[sensor_name]

use_binning = st.sidebar.checkbox("Enable 2x2 Binning", value=False, help="Combines 4 pixels into 1. Increases light sensitivity but halves resolution.")

rotate_90 = st.sidebar.checkbox("Rotate Camera 90°", value=False, help="Swaps the sensor width and height (Portrait Mode).")
if rotate_90:
    sensor = sensor.copy()
    sensor["width_px"], sensor["height_px"] = sensor["height_px"], sensor["width_px"]

wavelength = st.sidebar.selectbox("Wavelength (nm)", [730, 780, 810, 850, 940], index=2)

is_stereo = st.sidebar.checkbox("Stereoscopic (Dual Camera)", value=False, help="Enable calculation for dual-camera setup.")
stereo_base_val = 0
stereo_align = "Horizontal"
stereo_ratio = 5 # Default

if is_stereo:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Stereo Settings")
    stereo_align = st.sidebar.radio("Alignment", ["Horizontal", "Vertical"], horizontal=True, help="Alignment of the two cameras.")
    
    # Ratio Slider
    ratio_options = [30, 20, 15, 10, 7.5, 5, 4, 3]
    ratio_help = """
    **Base-to-Height Ratio (Distance : Stereo Base)**
    * **1:30 (Min):** Like human vision. High overlap, lower depth precision.
    * **1:10:** Good balance for general use.
    * **1:5 (Excellent):** Industry standard for photogrammetry. High accuracy.
    * **1:3:** Maximum accuracy, but significantly reduced overlap.
    """
    stereo_ratio = st.sidebar.select_slider("Base-to-Height Ratio (1:x)", options=ratio_options, value=5, help=ratio_help)
    
    curr_dist = st.session_state.get('distance', 430)
    stereo_base_val = int(curr_dist / stereo_ratio)

st.sidebar.divider()
st.sidebar.subheader("Optimization Targets")
target_res = st.sidebar.number_input("Min Resolution (px/mm)", value=4.0, step=0.1, help="Minimum pixels per millimeter required on the ball surface.")
target_bright = st.sidebar.number_input("Min Brightness (%)", value=100.0, step=10.0, help="Minimum relative brightness compared to the baseline setup.")
if 'target_min_dist' not in st.session_state: st.session_state.target_min_dist = 254
tmd_lbl = f"Min Distance Perpendicular to Swing (mm) - {st.session_state.target_min_dist/25.4:.1f}\""
target_min_dist = st.sidebar.number_input(tmd_lbl, min_value=100, max_value=1000, step=10, help="Closest allowed physical distance from Camera to Tee.", key="target_min_dist")
target_min_vla = st.sidebar.number_input("Min Vert Launch Angle (deg)", value=0.0, step=1.0, help="Required vertical floor angle (0 deg means camera sees the floor).")

coc_help = """
**In simple terms: Blur Tolerance.**
* **1.0 (Strict):** You demand razor-sharp pixels. (Smaller Focus Zone)
* **3.0 (Lenient):** You accept slight softness. (Larger Focus Zone)
"""
coc_mult = st.sidebar.slider("Circle of Confusion (px)", 1.0, 3.0, 2.0, 0.1, help=coc_help)

st.sidebar.divider()
st.sidebar.header("Ball Data")
include_club = st.sidebar.checkbox("Include Club Data", value=False, help="Adds tracking lines 4in below and 1in above tee.")
num_pos = st.sidebar.number_input("Number of Positions", min_value=2, value=2, step=1, help="Number of ball exposures to capture.")
if 'first_pos' not in st.session_state: st.session_state.first_pos = 152.4
fp_lbl = f"First Image Position (mm) - {st.session_state.first_pos/25.4:.1f}\""
first_pos = st.sidebar.number_input(fp_lbl, step=10.0, help="Distance from Tee to the FIRST ball image.", key="first_pos")
if 'spacing' not in st.session_state: st.session_state.spacing = 64.0
sp_lbl = f"Position Spacing (mm) - {st.session_state.spacing/25.4:.1f}\""
spacing = st.sidebar.number_input(sp_lbl, step=1.0, help="Distance between sequential ball images.", key="spacing")
st.sidebar.caption(f"Ref: Golf Ball Dia = {BALL_DIAMETER_MM} mm")

# --- STATE ---
if 'focal' not in st.session_state: st.session_state.focal = 6.0
if 'aperture' not in st.session_state: st.session_state.aperture = 1.2
if 'distance' not in st.session_state: st.session_state.distance = 430
if 'dist_parallel' not in st.session_state: st.session_state.dist_parallel = 127.0 # Default = 1st ball - 1 inch
if 'focus_offset' not in st.session_state: st.session_state.focus_offset = 0
if 'cam_z' not in st.session_state: st.session_state.cam_z = 0
if 'last_club_state' not in st.session_state: st.session_state.last_club_state = include_club

# Initialize Parallel Distance Once if not set (Smart Init)
if 'dist_parallel_init' not in st.session_state:
    st.session_state.dist_parallel_init = True
    # Calc default FOV width
    px_mm = (sensor["pixel_size"]) / 1000.0
    sensor_w = (sensor["width_px"]) * px_mm
    def_fov_w = (sensor_w * 430) / 6.0
    # Center = Bottom + Width/2
    # Default Bottom = 1st Ball (152.4) - 1" (25.4) = 127
    st.session_state.dist_parallel = int(127.0 + (def_fov_w / 2))

# Check if club state changed to update defaults
if st.session_state.last_club_state != include_club:
    st.session_state.last_club_state = include_club
    
    bin_factor = 2 if use_binning else 1
    px_mm = (sensor["pixel_size"] * bin_factor) / 1000
    sensor_w = (sensor["width_px"] / bin_factor) * px_mm
    eff_fov_w = (sensor_w * st.session_state.distance) / st.session_state.focal
    
    if is_stereo and stereo_align == "Horizontal":
        eff_fov_w = max(0, eff_fov_w - stereo_base_val)
        
    if include_club:
        st.session_state.dist_parallel = int(-127.0 + (eff_fov_w / 2)) # Bottom at -5"
    else:
        st.session_state.dist_parallel = int((first_pos - 25.4) + (eff_fov_w / 2)) # Bottom at 1st Ball - 1"

# --- SMART AUTO OPTIMIZER ---
# Top-level optimization row
c_opt1, c_opt2, c_opt3 = st.columns([0.25, 0.45, 0.3])

with c_opt2:
    min_coverage_pct = st.slider("Min Image Circle Coverage (%)", 50, 100, 90, 5)

with c_opt3:
    st.write("") # Spacer to align
    st.write("") 
    include_varifocal = st.checkbox("Include Varifocal Lenses", value=True)

# Re-calculate compatible lenses based on checkbox state
compatible_lenses = get_compatible_lenses(sensor, min_coverage_pct, include_varifocal)

with c_opt1:
    st.markdown("### ")
    if st.button("✨ Optimize System", help="Analytically finds the best configuration. Prioritizes maximizing Depth of Field (Focus Zone) first, then maximizes Perpendicular Distance."):
        valid_configs = []
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        
        # Iterate through COMPATIBLE LENSES only
        for l_data in compatible_lenses:
            f = l_data[1]
            aper = l_data[2]
            
            # 1. Analytical Max Distance for Resolution
            # Res = f / (px_mm * d)  =>  d <= f / (px_mm * TargetRes)
            d_res = f / (px_mm * target_res)
            
            # 2. Analytical Max Distance for Brightness
            # Brightness is proportional to 1/d^2. 
            # We solve for d where Brightness == TargetBright
            base_params = st.session_state.base_params
            base_px_area = base_params["sensor"]["pixel_size"] ** 2
            base_wavelength = base_params.get('wavelength', 810)
            base_qe = base_params["sensor"]["qe"].get(base_wavelength, base_params["sensor"]["qe"].get(810, 0.2))
            base_score = (base_qe * base_px_area) / ((base_params["aperture"]**2) * (base_params["distance"]**2))
            
            qe = sensor["qe"].get(wavelength, sensor["qe"].get(810, 0.2))
            px_size_um = sensor["pixel_size"] * bin_factor
            # CurrentScore = (qe * px^2) / (aper^2 * d^2)
            # TargetScore = (target_bright / 100) * base_score
            # d^2 <= (qe * px^2) / (aper^2 * TargetScore)
            target_score = (target_bright / 100.0) * base_score
            if target_score > 0:
                d_bright_sq = (qe * (px_size_um**2)) / ((aper**2) * target_score)
                d_bright = math.sqrt(d_bright_sq)
            else:
                d_bright = 10000

            # 3. Determine Optimal Distance
            # We want the largest distance that satisfies both constraints (and safety limit)
            max_valid_dist = int(min(d_res, d_bright, 1000))
            
            if max_valid_dist >= target_min_dist:
                found_d_for_lens = max_valid_dist
                trial_base = int(found_d_for_lens / stereo_ratio) if is_stereo else 0
                
                # Calculate Parallel Offset for this distance
                sensor_w_inner = (sensor["width_px"] / bin_factor) * px_mm
                eff_fov_w_inner = (sensor_w_inner * found_d_for_lens) / f
                if is_stereo and stereo_align == "Horizontal":
                    eff_fov_w_inner = max(0, eff_fov_w_inner - trial_base)
                
                if include_club: found_parallel_for_lens = -127.0 + (eff_fov_w_inner / 2)
                else: found_parallel_for_lens = (first_pos - 25.4) + (eff_fov_w_inner / 2)
            
                # 4. Optimize Focus Offset using Golden Section Search
                def focus_error_func(off_val):
                    m = calculate_metrics(sensor, use_binning, wavelength, f, aper, found_d_for_lens,
                                          include_club, num_pos, first_pos, spacing, off_val, coc_mult, 0, found_parallel_for_lens, True,
                                          is_stereo, trial_base, stereo_align)
                    if m['far_limit'] > 99999: return 0.0 # Hyperfocal achieved
                    # We want distance to be the midpoint of near and far
                    return abs((found_d_for_lens - m['near_limit']) - (m['far_limit'] - found_d_for_lens))

                best_off = int(golden_section_search(focus_error_func, -400, 200, tol=1.0))
                
                flight_d = first_pos + (num_pos - 1) * spacing
                m_z0 = calculate_metrics(sensor, use_binning, wavelength, f, aper, found_d_for_lens, 
                                        include_club, num_pos, first_pos, spacing, best_off, coc_mult, 0, found_parallel_for_lens, True,
                                        is_stereo, trial_base, stereo_align)
                
                current_min_v = m_z0['min_v_angle']
                deg_diff = current_min_v - target_min_vla
                drop_mm = math.tan(math.radians(deg_diff)) * flight_d
                optimal_cam_z = int(0 - drop_mm)
                
                final_m = calculate_metrics(sensor, use_binning, wavelength, f, aper, found_d_for_lens, 
                                          include_club, num_pos, first_pos, spacing, best_off, coc_mult, optimal_cam_z, found_parallel_for_lens, True,
                                          is_stereo, trial_base, stereo_align)
                
                if final_m['min_h_angle'] is not None and final_m['min_v_angle'] <= target_min_vla + 0.5:
                    valid_configs.append({
                        "focal": f, "aperture": aper, "dist": found_d_for_lens, 
                        "offset": best_off, "cam_z": optimal_cam_z,
                        "parallel": found_parallel_for_lens,
                        "dof": final_m['dof'], "model": l_data[0]
                    })
        
        if valid_configs:
            valid_configs.sort(key=lambda x: (x['dof'], x['dist']), reverse=True)
            winner = valid_configs[0]
            
            # Update session state with winner
            st.session_state.focal = winner['focal']
            st.session_state.aperture = winner['aperture']
            st.session_state.distance = winner['dist']
            st.session_state.focus_offset = winner['offset']
            st.session_state.cam_z = winner['cam_z']
            st.session_state.dist_parallel = int(winner['parallel'])
            st.rerun()
        else:
            st.error("❌ No configuration found satisfying Targets.")

st.divider()

# --- PREPARE LENS DATA FOR SLIDERS ---
# 1. Get Global Min/Max Focal & Aperture from ALL lenses (to define slider ranges)
all_focals = sorted(list(set([l[1] for l in LENS_DATABASE])))
all_apertures = sorted(list(set([l[2] for l in LENS_DATABASE])))
min_f, max_f = min(all_focals), max(all_focals)
min_a, max_a = min(all_apertures), max(all_apertures)

# --- MANUAL INPUTS ---
c1, c2, c3 = st.columns(3)
with c1: 
    # Use standard slider with full range (0.1 increments)
    st.slider("Focal Length (mm)", min_value=float(min_f), max_value=float(max_f), step=0.1, key="focal")
    
    if st.button("Optimize Lens Only", help="Finds the best real lens focal length for the current distance."):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        ideal_f = st.session_state.distance * px_mm * target_res
        
        # Find nearest REAL lens focal
        compatible_focals = sorted(list(set([l[1] for l in compatible_lenses])))
        st.session_state.focal = find_nearest(compatible_focals, ideal_f)
        st.rerun()
        
with c2: 
    # Use standard slider with full range (0.1 increments)
    st.slider("Aperture (f/)", min_value=float(min_a), max_value=float(max_a), step=0.1, key="aperture")

    if st.button("Optimize f-stop Only", help="Finds the best real aperture (for brightness/DOF) given the current focal."):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        qe = sensor["qe"].get(wavelength, sensor["qe"].get(810, 0.2))
        base_params = st.session_state.base_params
        base_px_area = base_params["sensor"]["pixel_size"] ** 2
        base_wavelength = base_params.get('wavelength', 810)
        base_qe = base_params["sensor"]["qe"].get(base_wavelength, base_params["sensor"]["qe"].get(810, 0.2))
        base_score = (base_qe * base_px_area) / ((base_params["aperture"]**2) * (base_params["distance"]**2))
        target_score = (target_bright / 100) * base_score
        if target_score > 0:
            f_sq = (qe * (px_size_um := sensor["pixel_size"] * bin_factor)**2) / (target_score * st.session_state.distance**2)
            max_f = math.sqrt(f_sq)
        else:
            max_f = 999

        # Look for real apertures in compatible lenses
        valid_apertures = sorted(list(set([l[2] for l in compatible_lenses])))
        valid_subset = [x for x in valid_apertures if x <= max_f]
        
        if valid_subset: st.session_state.aperture = max(valid_subset) 
        else: st.session_state.aperture = valid_apertures[0] 
        st.rerun()

with c3: 
    dist_lbl = f"Distance Perpendicular to Swing (mm) - {st.session_state.distance/25.4:.1f}\""
    st.slider(dist_lbl, 100, 1000, step=1, help="Horizontal distance from Lens to Tee.", key="distance")
    if st.button("Optimize Dist Only", help="Finds the maximum distance that satisfies the Resolution and Brightness targets."):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        max_res_dist = int(st.session_state.focal / (px_mm * target_res))
        
        best_d = None
        start_d = min(max_res_dist, 1000)
        
        for d in range(start_d, 100, -10): 
             # Use current focus offset (no optimization)
             trial_base = int(d / stereo_ratio) if is_stereo else 0
             base_chk = calculate_metrics(sensor, use_binning, wavelength, st.session_state.focal, st.session_state.aperture, d,
                                    include_club, num_pos, first_pos, spacing, st.session_state.focus_offset, coc_mult, 0, st.session_state.dist_parallel, True,
                                    is_stereo, trial_base, stereo_align)
             if base_chk['bright'] >= target_bright:
                 best_d = d
                 break 
        
        if best_d and best_d >= target_min_dist:
            st.session_state.distance = best_d
            st.rerun()
        else:
            st.error("Cannot satisfy constraints.")

# --- LENS MATCHING LOGIC ---
match_lens = None
for l in compatible_lenses:
    if math.isclose(l[1], st.session_state.focal, abs_tol=0.05) and math.isclose(l[2], st.session_state.aperture, abs_tol=0.05):
        match_lens = l[0]
        break

if match_lens:
    st.success(f"**Lens Model Found:** {match_lens}")
else:
    st.warning(f"⚠️ Standard lens may not exist with these exact specs ({st.session_state.focal}mm f/{st.session_state.aperture})")

c4, c5, c6 = st.columns(3)
with c4: 
    fo_lbl = f"Focus Offset (mm) - {st.session_state.focus_offset/25.4:.1f}\""
    st.slider(fo_lbl, -400, 200, step=5, help="Shifts the focal plane closer (-) or further (+).", key="focus_offset")
    if st.button("Optimize Focus Only", help="Adjusts focus offset to center the Depth of Field around the Tee."):
        best_off = 0
        best_diff = 9999
        for off in range(-400, 200, 5):
            m = calculate_metrics(sensor, use_binning, wavelength, st.session_state.focal, st.session_state.aperture, st.session_state.distance,
                                include_club, num_pos, first_pos, spacing, off, coc_mult, 0, st.session_state.dist_parallel, True,
                                is_stereo, stereo_base_val, stereo_align)
            near = m['near_limit']
            far = m['far_limit']
            if far > 99999: diff = 0 
            else: diff = abs((st.session_state.distance - near) - (far - st.session_state.distance))
            if diff < best_diff:
                best_diff = diff
                best_off = off
        st.session_state.focus_offset = best_off
        st.rerun()

with c5: 
    cz_lbl = f"Vert Cam Offset (mm) - {st.session_state.cam_z/25.4:.1f}\""
    st.slider(cz_lbl, -500, 500, step=5, help="0 = Bottom of FOV aligns with Tee level (0°). Positive values raise the camera.", key="cam_z")
    if st.button("Optimize Vert Cam Only", help="Adjusts vertical height to meet the Min Vert Launch Angle target."):
        flight_d = first_pos + (num_pos - 1) * spacing
        offset_needed = math.tan(math.radians(target_min_vla)) * flight_d
        st.session_state.cam_z = int(offset_needed)
        st.rerun()

with c6:
    dp_lbl = f"Distance Parallel to Swing (mm) - {st.session_state.dist_parallel/25.4:.1f}\""
    st.slider(dp_lbl, -200, 600, step=1, help="Shift Camera Left/Right along the swing line.", key="dist_parallel")
    if st.button("Optimize Parallel Only", help="Aligns bottom edge of FOV based on selected mode (1 inch below ball or -5 inches for club)."):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        sensor_w = (sensor["width_px"] / bin_factor) * px_mm
        eff_fov_w = (sensor_w * st.session_state.distance) / st.session_state.focal
        
        if is_stereo and stereo_align == "Horizontal":
            eff_fov_w = max(0, eff_fov_w - stereo_base_val)
            
        if include_club:
            st.session_state.dist_parallel = int(-127.0 + (eff_fov_w / 2))
        else:
            st.session_state.dist_parallel = int((first_pos - 25.4) + (eff_fov_w / 2))
        st.rerun()

# --- CALCULATIONS ---
vals = calculate_metrics(sensor, use_binning, wavelength, st.session_state.focal, st.session_state.aperture, st.session_state.distance,
                        include_club, num_pos, first_pos, spacing, st.session_state.focus_offset, coc_mult, st.session_state.cam_z, st.session_state.dist_parallel, False,
                        is_stereo, stereo_base_val, stereo_align)

base_params = st.session_state.base_params

base_fov_h = (base_params["sensor"]["height_px"] * base_params["sensor"]["pixel_size"] / 1000 * base_params["distance"]) / base_params["focal"]
base_fov_w = (base_params["sensor"]["width_px"] * base_params["sensor"]["pixel_size"] / 1000 * base_params["distance"]) / base_params["focal"]
base_offset = base_params["height_target"] - (base_fov_h / 2)

if "first_pos" in base_params:
    baseline_first_pos = base_params["first_pos"]
else:
    baseline_first_pos = base_params["y_pos"] - (base_fov_w / 2) + 25.4

base_res = calculate_metrics(
    base_params["sensor"], base_params["binning"], base_params.get('wavelength', 810), 
    base_params["focal"], base_params["aperture"], base_params["distance"],
    base_params.get("include_club", False), num_pos, baseline_first_pos, spacing, base_params.get("focus_offset", 0), coc_mult, base_offset, base_params["y_pos"], False,
    base_params.get("is_stereo", False), base_params.get("stereo_base", 0), base_params.get("stereo_align", "Horizontal")
)

# --- RESULTS TABLE ---
def fmt_dof(dof, dn, df): return f"{dof:.1f} mm ({dof/25.4:.1f}\") [{dn:.1f} mm ({dn/25.4:.1f}\") - {df:.1f} mm ({df/25.4:.1f}\")]"
def fmt_angle(min_val, max_val):
    if min_val is None: return "NOT VISIBLE"
    return f"[{min_val:+.1f}°, {max_val:+.1f}°]"

metrics = [
    ("Lens", f"{base_params['focal']}mm f/{base_params['aperture']}", f"{st.session_state.focal}mm f/{st.session_state.aperture}", "", False),
    ("Distance Perpendicular", base_params["distance"], st.session_state.distance, "mm", False),
    ("Distance Parallel (Center)", base_params["y_pos"], st.session_state.dist_parallel, "mm", False),
]

if is_stereo or base_params.get("is_stereo", False):
    b_sb = base_params.get("stereo_base", 0)
    b_txt = f"{b_sb}mm ({b_sb/25.4:.1f}\")" if base_params.get("is_stereo", False) else "N/A"
    n_txt = f"{stereo_base_val}mm ({stereo_base_val/25.4:.1f}\")" if is_stereo else "N/A"
    metrics.append(("Stereo Base (Camera Separation)", b_txt, n_txt, "", False))

metrics.extend([
    ("Camera Height", base_res['total_cam_height'], vals['total_cam_height'], " mm", False),
    ("FOV Width" if not is_stereo else "FOV Width (Overlap)", (base_res['fov_w'], base_params["distance"]), (vals['fov_w'], st.session_state.distance), "fov_complex", True),
    ("FOV Height", (base_res['fov_h'], base_params["distance"]), (vals['fov_h'], st.session_state.distance), "fov_complex", True),
    ("Resolution", base_res['res'], vals['res'], " px/mm", True),
    ("Brightness", (base_res['bright'], base_params.get('wavelength', 810)), (vals['bright'], wavelength), "brightness_complex", True),
    ("Focus Zone", 
     (base_res['dof'], base_res['near_limit'], base_res['far_limit']), 
     (vals['dof'], vals['near_limit'], vals['far_limit']), "dof_complex", True),
    ("Horiz Launch Angle", (base_res['min_h_angle'], base_res['max_h_angle']), (vals['min_h_angle'], vals['max_h_angle']), "angle_complex", True),
    ("Vert Launch Angle", (base_res['min_v_angle'], base_res['max_v_angle']), (vals['min_v_angle'], vals['max_v_angle']), "angle_complex", True),
])

data = []
for name, base, new_val, unit, diff in metrics:
    row = {"Metric": name, "Baseline": "", "Your Setup": "", "Change": "", "status": "neutral"}
    
    if unit == "dof_complex":
        b_tot, b_near, b_far = base
        n_tot, n_near, n_far = new_val
        row["Baseline"] = fmt_dof(b_tot, b_near, b_far)
        row["Your Setup"] = fmt_dof(n_tot, n_near, n_far)
        pct_tot = ((n_tot - b_tot)/b_tot)*100
        pct_near = ((n_near - b_near)/b_near)*100
        pct_far = ((n_far - b_far)/b_far)*100
        row["Change"] = f"{pct_tot:+.1f}% [{pct_near:+.1f}%, {pct_far:+.1f}%]"
        row["status"] = "good" if pct_tot >= 0 else "bad"
    elif unit == "brightness_complex":
        b_val, b_wl = base
        n_val, n_wl = new_val
        row["Baseline"] = f"{b_val:.1f}% @{b_wl}nm"
        row["Your Setup"] = f"{n_val:.1f}% @{n_wl}nm"
        pct_diff = n_val - b_val
        row["Change"] = f"{pct_diff:+.1f}%"
        row["status"] = "pass" if n_val >= target_bright else "fail"
    elif unit == "angle_complex":
        b_min, b_max = base
        n_min, n_max = new_val
        if b_min is None or n_min is None:
            row["Baseline"] = "N/A"
            row["Your Setup"] = "NOT VISIBLE"
            row["status"] = "fail"
        else:
            row["Baseline"] = fmt_angle(b_min, b_max)
            row["Your Setup"] = fmt_angle(n_min, n_max)
            b_width = b_max - b_min
            n_width = n_max - n_min
            if abs(b_min) < 0.01: pct_min = 0 
            else: pct_min = (b_min - n_min) / abs(b_min) * 100
            if abs(b_max) < 0.01: pct_max = 0
            else: pct_max = (n_max - b_max) / abs(b_max) * 100
            row["Change"] = f"[{pct_min:+.1f}%, {pct_max:+.1f}%]"
            row["status"] = "good" if n_width >= b_width else "bad"
    elif unit == "fov_complex":
        b_val, b_dist = base
        n_val, n_dist = new_val
        b_deg = math.degrees(2 * math.atan((b_val / 2) / b_dist))
        n_deg = math.degrees(2 * math.atan((n_val / 2) / n_dist))
        row["Baseline"] = f"{b_val:.1f} mm ({b_val/25.4:.1f}\") [{b_deg:.1f}°]"
        row["Your Setup"] = f"{n_val:.1f} mm ({n_val/25.4:.1f}\") [{n_deg:.1f}°]"
        pct = ((n_val - b_val)/b_val)*100
        row["Change"] = f"{pct:+.1f}%"
        row["status"] = "good" if pct >= 0 else "bad"
    elif unit == "": 
        row["Baseline"] = base
        row["Your Setup"] = new_val
        row["Change"] = "" 
    else: 
        if "mm" in unit and "px" not in unit:
            row["Baseline"] = f"{base:.1f}{unit} ({base/25.4:.1f}\")"
            row["Your Setup"] = f"{new_val:.1f}{unit} ({new_val/25.4:.1f}\")"
        else:
            row["Baseline"] = f"{base:.1f}{unit}"
            row["Your Setup"] = f"{new_val:.1f}{unit}"
        if diff: 
            pct = ((new_val - base)/base)*100
            row["Change"] = f"{pct:+.1f}%"
            if name == "Resolution": row["status"] = "pass" if new_val >= target_res else "fail"
            elif name == "Brightness": row["status"] = "pass" if new_val >= target_bright else "fail"
            else: row["status"] = "good" if pct >= 0 else "bad"
        else: 
            row["Change"] = ""
    data.append(row)

df = pd.DataFrame(data)
def style_fn(styler):
    def color_rows(row):
        c = ''
        if row['status'] in ['pass','good']: c = 'background-color: rgba(144, 238, 144, 0.3)'
        elif row['status'] in ['fail','bad']: c = 'background-color: rgba(255, 99, 71, 0.3)'
        return [c] * len(row)
    return styler.apply(color_rows, axis=1)

# Dynamic height calculation to prevent scrollbars
row_height = 35 
header_height = 38 
total_height = (len(df) * row_height) + header_height + 5

st.dataframe(
    style_fn(df.style),
    width="stretch",
    hide_index=True,
    column_order=["Metric", "Baseline", "Your Setup", "Change"],
    height=total_height
)

b_c1, b_c2, b_c3, b_c4 = st.columns([2, 1, 1, 1])
with b_c2:
    if st.button("Reset Baseline", help="Restores the original hardcoded baseline."):
        st.session_state.base_params = DEFAULT_BASE_PARAMS.copy()
        st.rerun()
with b_c3:
    if st.button("Set Current as Baseline", help="Updates the Baseline column to match your current configuration."):
        st.session_state.base_params = {
            "sensor": sensor.copy(),
            "focal": st.session_state.focal,
            "aperture": st.session_state.aperture,
            "distance": st.session_state.distance,
            "height_target": vals['total_cam_height'],
            "y_pos": st.session_state.dist_parallel,
            "wavelength": wavelength,
            "binning": use_binning,
            "focus_offset": st.session_state.focus_offset,
            "first_pos": st.session_state.first_pos,
            "include_club": include_club,
            "is_stereo": is_stereo,
            "stereo_base": stereo_base_val,
            "stereo_align": stereo_align
        }
        st.rerun()

# --- PLOTS ---
sch_c1, sch_c2 = st.columns(2)
x_max = max(base_params["distance"], st.session_state.distance) + 250
balls_max_y = max(first_pos, baseline_first_pos) + (num_pos * spacing) + 100
fov_max_y = max(base_res["fov_top"], vals["fov_top"]) + 50
fov_min_y = min(base_res["fov_bottom"], vals["fov_bottom"]) - 50
y_limits = (fov_min_y, max(balls_max_y, fov_max_y))

# Ensure x-min is wide enough for club data if needed
min_x_limit = -200
if include_club:
    min_x_limit = -250

# Global Plot Limits Calculation
global_y_min = min(base_res["fov_bottom"], vals["fov_bottom"], -50)
if include_club:
    global_y_min = min(global_y_min, -120)

global_y_max = max(base_res["fov_top"], vals["fov_top"], balls_max_y) + 50
global_x_max = max(base_params["distance"], st.session_state.distance) + 250

with sch_c1:
    st.pyplot(plot_schematic("Baseline", base_params["distance"], base_res, num_pos, baseline_first_pos, spacing, (-200, global_x_max), (global_y_min, global_y_max), base_params.get("include_club", False)))
with sch_c2:
    st.pyplot(plot_schematic("Your Setup", st.session_state.distance, vals, num_pos, first_pos, spacing, (-200, global_x_max), (global_y_min, global_y_max), include_club))

lm_c1, lm_c2 = st.columns(2)
# Ensure LM view is wide enough for club data (-101.6mm)
base_min_x = min(base_res["fov_center"] - base_res["fov_w"]/2, vals["fov_center"] - vals["fov_w"]/2, -50) - 20
if include_club or base_params.get("include_club", False):
    base_min_x = min(base_min_x, -150)

all_min_x = base_min_x
all_max_x = max(base_res["fov_center"] + base_res["fov_w"]/2, vals["fov_center"] + vals["fov_w"]/2) + 50
all_max_y = max(base_res["fov_top_z_far"], vals["fov_top_z_far"]) + 50

with lm_c1:
    base_inc_club = base_params.get("include_club", False)
    start_n_base = 3 if base_inc_club else 1
    st.pyplot(plot_sensor_view_final("Baseline", base_res, num_pos, baseline_first_pos, spacing, start_n_base, (all_min_x, all_max_x), (-50, all_max_y), include_club=base_inc_club))
with lm_c2:
    start_n = 3 if include_club else 1
    st.pyplot(plot_sensor_view_final("Your Setup", vals, num_pos, first_pos, spacing, start_n, (all_min_x, all_max_x), (-50, all_max_y), include_club=include_club))