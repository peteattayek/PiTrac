import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="SimCam Optics Calculator", layout="wide")

BALL_DIAMETER_MM = 42.67
BALL_RADIUS_MM = BALL_DIAMETER_MM / 2

# BASELINE HARDWARE (FIXED REFERENCE)
BASE_PARAMS = {
    "sensor": {
        "width_px": 1440, "height_px": 1080, "pixel_size": 3.45, 
        "format": "1/2.9", "qe": {810: 0.21}
    },
    "focal": 6.0,
    "aperture": 1.2,
    "distance": 430,      # Fixed X (Camera Dist)
    "height_target": 90,  # Fixed Z (Camera Height)
    "y_pos": 530,         # Fixed Y (Horizontal Center)
    "wavelength": 810,
    "binning": False
}

# REAL WORLD LENS CATALOG
REAL_FOCAL_LENGTHS = [2.1, 2.5, 2.8, 3.6, 4.0, 6.0, 8.0, 12.0, 16.0, 25.0]
REAL_APERTURES = [1.2, 1.4, 1.6, 1.8, 2.0, 2.4, 2.8, 4.0, 5.6, 8.0]

# SENSOR DATABASE
SENSORS = {
    "IMX296 (1.6MP Global Shutter)": {
        "width_px": 1440, "height_px": 1080, "pixel_size": 3.45, "format": "1/2.9",
        "shutter": "Global", "nir_tech": None,
        "qe": {810: 0.21, 850: 0.15, 940: 0.07}
    },
    "OV9281 (1.0MP Global Shutter)": {
        "width_px": 1280, "height_px": 800, "pixel_size": 3.0, "format": "1/4",
        "shutter": "Global", "nir_tech": None,
        "qe": {810: 0.28, 850: 0.20, 940: 0.09}
    },
    "AR0234 (2.3MP Global Shutter)": {
        "width_px": 1920, "height_px": 1200, "pixel_size": 3.0, "format": "1/2.6",
        "shutter": "Global", "nir_tech": None,
        "qe": {810: 0.25, 850: 0.19, 940: 0.07}
    },
    "OS08A20 (8.3MP Rolling Shutter)": {
        "width_px": 3840, "height_px": 2160, "pixel_size": 2.0, "format": "1/1.8",
        "shutter": "Rolling", "nir_tech": "Nyxel™",
        "qe": {810: 0.70, 850: 0.60, 940: 0.40}
    },
    "OG05B1B (5.0MP Global Shutter)": {
        "width_px": 2592, "height_px": 1944, "pixel_size": 2.2, "format": "1/2.5",
        "shutter": "Global", "nir_tech": "Nyxel™",
        "qe": {810: 0.65, 850: 0.60, 940: 0.40}
    },
    "IMX678 (8.3MP Rolling Shutter)": {
        "width_px": 3840, "height_px": 2160, "pixel_size": 2.0, "format": "1/1.8",
        "shutter": "Rolling", "nir_tech": "Starvis 2",
        "qe": {810: 0.50, 850: 0.45, 940: 0.25}
    },
     "AR0822 (8.3MP Rolling Shutter)": {
        "width_px": 3840, "height_px": 2160, "pixel_size": 2.0, "format": "1/1.8",
        "shutter": "Rolling", "nir_tech": "NIR+",
        "qe": {810: 0.58, 850: 0.49, 940: 0.29}
    }
}

# Generate Sensor Tooltip
sensor_help_text = """
| Sensor | Shutter | Pixel (µm) | MP | W x H | 2x2 Pixel | 2x2 MP | 2x2 WxH |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
"""
for name, s in SENSORS.items():
    short_name = name.split(' ')[0]
    shutter = s['shutter']
    px = s['pixel_size']
    w, h = s['width_px'], s['height_px']
    mp = (w * h) / 1_000_000
    bin_px = px * 2
    bin_mp = mp / 4
    bin_w = int(w / 2)
    bin_h = int(h / 2)
    sensor_help_text += f"| {short_name} | {shutter} | {px} | {mp:.1f} | {w}x{h} | {bin_px} | {bin_mp:.2f} | {bin_w}x{bin_h} |\n"

# --- CALCULATION LOGIC ---
def find_nearest(array, value):
    idx = (math.fabs(array[0] - value))
    near = array[0]
    for val in array:
        if math.fabs(val - value) < idx:
            idx = math.fabs(val - value)
            near = val
    return near

def calculate_metrics(sensor, binning, wavelength, focal, f_stop, dist, 
                      include_club, num_pos, first_pos, spacing, focus_offset, 
                      coc_mult, cam_z_offset, fixed_y_center=None, ignore_ball_fit=False):
    bin_factor = 2 if binning else 1
    px_size_um = sensor["pixel_size"] * bin_factor
    px_size_mm = px_size_um / 1000.0
    width_px = sensor["width_px"] / bin_factor
    height_px = sensor["height_px"] / bin_factor
    sensor_w = width_px * px_size_mm
    sensor_h = height_px * px_size_mm
    
    # FOV
    fov_w = (sensor_w * dist) / focal
    fov_h = (sensor_h * dist) / focal
    
    # FOV Position (Horizontal)
    if fixed_y_center is not None:
        fov_center = fixed_y_center
        fov_top = fov_center + (fov_w / 2) 
        fov_bottom = fov_center - (fov_w / 2)
    else:
        if include_club:
            fov_bottom = -152.4
        else:
            fov_bottom = first_pos - 25.4
        fov_top = fov_bottom + fov_w
        fov_center = (fov_top + fov_bottom) / 2
    
    # Camera Height Logic (Vertical)
    base_cam_height = fov_h / 2
    total_cam_height = base_cam_height + cam_z_offset
    
    res = width_px / fov_w
    
    # DOF
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
    
    # Brightness
    base_px_area = BASE_PARAMS["sensor"]["pixel_size"] ** 2
    base_score = (BASE_PARAMS["sensor"]["qe"][810] * base_px_area) / ((BASE_PARAMS["aperture"]**2) * (BASE_PARAMS["distance"]**2))
    
    qe = sensor["qe"].get(wavelength, 0.2)
    current_score = (qe * (px_size_um**2)) / ((f_stop**2) * (dist**2))
    bright_pct = (current_score / base_score) * 100
    
    # --- VALIDITY CHECK ---
    is_valid = True
    if not ignore_ball_fit:
        for i in range(num_pos):
            ball_center = first_pos + (i * spacing)
            if (ball_center - BALL_RADIUS_MM) < fov_bottom or (ball_center + BALL_RADIUS_MM) > fov_top:
                is_valid = False
                break
            
    # --- LAUNCH ANGLES ---
    safe_near = max(0, dist - dn)
    flight_dist = first_pos + (num_pos - 1) * spacing
    if flight_dist <= 0: flight_dist = 1
    
    min_h_angle = -math.degrees(math.atan(safe_near / flight_dist))
    if df > 99999:
         max_h_angle = 90.0
    else:
         safe_far = max(0, df - dist)
         max_h_angle = math.degrees(math.atan(safe_far / flight_dist))
    
    # Vertical Angles (FULL BALL CHECK)
    fov_bottom_z = total_cam_height - (fov_h / 2)
    fov_top_z = total_cam_height + (fov_h / 2)
    
    # Min VLA: Ball Bottom (0) -> Window Bottom
    min_v_rad = math.atan(fov_bottom_z / flight_dist)
    min_v_angle = math.degrees(min_v_rad)
    
    # Max VLA: Ball Top (Diameter) -> Window Top
    max_v_rad = math.atan((fov_top_z - BALL_DIAMETER_MM) / flight_dist)
    max_v_angle = math.degrees(max_v_rad)

    if not is_valid and not ignore_ball_fit:
        min_h_angle = None
        max_h_angle = None
        min_v_angle = None
        max_v_angle = None

    return {
        "res": res, "dof": dof, "fov_w": fov_w, "fov_h": fov_h,
        "bright": bright_pct, "px_size_mm": px_size_mm, "qe": qe,
        "near_limit": dn, "far_limit": df,
        "min_h_angle": min_h_angle, "max_h_angle": max_h_angle,
        "min_v_angle": min_v_angle, "max_v_angle": max_v_angle,
        "fov_bottom": fov_bottom, "fov_top": fov_top,
        "fov_center": fov_center,
        "total_cam_height": total_cam_height,
        "focus_dist": focus_dist,
        "safe_near_dev": safe_near,
        "safe_far_dev": max(0, df - dist) if df < 99999 else 9999,
        "flight_dist": flight_dist,
        "min_v_rad": min_v_rad,
        "max_v_rad": max_v_rad
    }

# --- PLOTTING FUNCTION (TOP DOWN) ---
def plot_schematic(title, dist_mm, fov_w_mm, fov_center_y, dof_near, dof_far, 
                  include_club, num_pos, first_pos, spacing,
                  x_max, y_limits, focus_dist,
                  safe_near_dev, safe_far_dev, flight_dist):
    
    fig, ax = plt.subplots(figsize=(5, 5), dpi=120) 
    
    fov_top = fov_center_y + (fov_w_mm / 2)
    fov_bottom = fov_center_y - (fov_w_mm / 2)
    
    # LM SQUARE
    lm_box = patches.Rectangle((-150, fov_center_y - 75), 150, 150, 
                               linewidth=1, edgecolor='black', facecolor='#222222', alpha=0.9, zorder=20)
    ax.add_patch(lm_box)
    ax.text(-75, fov_center_y, "LM", ha='center', va='center', color='white', fontweight='bold', zorder=21)

    # FOV Cone
    fov_x = [0, dist_mm, dist_mm]
    fov_y = [fov_center_y, fov_top, fov_bottom]
    ax.fill(fov_x, fov_y, alpha=0.15, color='skyblue', zorder=1)
    ax.plot([0, dist_mm], [fov_center_y, fov_top], color='skyblue', linestyle='--', zorder=1)
    ax.plot([0, dist_mm], [fov_center_y, fov_bottom], color='skyblue', linestyle='--', zorder=1)

    # DOF Zone
    plot_far = min(dof_far, dist_mm + 500)
    dof_rect = patches.Rectangle((dof_near, fov_bottom), plot_far - dof_near, fov_w_mm, 
                                 linewidth=1, edgecolor='green', facecolor='green', alpha=0.15, zorder=2, label='Focus Zone')
    ax.add_patch(dof_rect)
    
    # Tee
    ax.axvline(dist_mm, color='red', linestyle=':', alpha=0.5, zorder=3)
    ax.plot(dist_mm, 0, 'kx', markersize=8, markeredgewidth=2, zorder=5)
    ax.text(dist_mm, -20, "Tee", ha='center', va='top', fontweight='bold', zorder=20)
    
    lbl_off = 35 
    
    # CLUB DATA LINES
    if include_club:
        club_y_min = -101.6 
        club_y_max = 25.4   
        cx_min = dof_near
        cx_max = min(dof_far, x_max + 100)
        ax.plot([cx_min, cx_max], [club_y_min, club_y_min], color='red', linestyle=':', linewidth=1.5, zorder=4)
        ax.text(dist_mm + lbl_off, club_y_min, "1", color='blue', fontweight='bold', va='center', zorder=20)
        ax.plot([cx_min, cx_max], [club_y_max, club_y_max], color='red', linestyle=':', linewidth=1.5, zorder=4)
        ax.text(dist_mm + lbl_off, club_y_max, "2", color='blue', fontweight='bold', va='center', zorder=20)
        start_num = 3
    else:
        start_num = 1
    
    # BALLS
    for i in range(num_pos):
        y = first_pos + (i * spacing)
        ax.add_patch(patches.Circle((dist_mm, y), BALL_RADIUS_MM, facecolor='red', edgecolor='black', linewidth=0.5, zorder=10))
        
        # Ghosts
        if flight_dist > 0: scale = y / flight_dist
        else: scale = 0
        near_offset = safe_near_dev * scale
        far_offset = safe_far_dev * scale
        
        ax.add_patch(patches.Circle((dist_mm - near_offset, y), BALL_RADIUS_MM, 
                                    linestyle=':', linewidth=1.5, edgecolor='red', facecolor='none', zorder=11))
        
        if safe_far_dev < 9000:
            ax.add_patch(patches.Circle((dist_mm + far_offset, y), BALL_RADIUS_MM, 
                                        linestyle=':', linewidth=1.5, edgecolor='red', facecolor='none', zorder=11))
            label_x = dist_mm + far_offset + 40
        else:
            label_x = dist_mm + lbl_off + 50
            
        ax.text(label_x, y, str(start_num + i), color='black', fontweight='bold', va='center', zorder=20)
        
    arrow_x = x_max - 50
    ax.arrow(arrow_x, 0, 0, 200, head_width=20, head_length=40, fc='k', ec='k', zorder=5)
    ax.text(arrow_x + 30, 100, "Swing Direction", rotation=90, va='center', zorder=5)

    ax.set_title(title + " (Top View)")
    ax.set_xlabel("Distance from Camera (mm)")
    ax.set_ylabel("Horizontal Position (mm)")
    
    ax.set_xlim(-200, x_max + 50)
    final_y_min = min(y_limits[0], -120)
    final_y_max = max(y_limits[1], 250)
    ax.set_ylim(final_y_min, final_y_max)
    ax.set_aspect('equal', adjustable='box') 
    ax.grid(True, linestyle=':', alpha=0.6)
    
    return fig

# --- PLOTTING FUNCTION (YZ SENSOR VIEW) ---
def plot_sensor_view_final(title, fov_w_mm, fov_h_mm, fov_center_x, cam_height, 
                     min_v_rad, max_v_rad, num_pos, first_pos, spacing, start_num,
                     fixed_xlims=None, fixed_ylims=None):
                     
    fig, ax = plt.subplots(figsize=(5, 5), dpi=120)
    
    # FOV Box (Centered at fov_center_x, cam_height)
    rect_left = fov_center_x - (fov_w_mm / 2)
    rect_bottom = cam_height - (fov_h_mm / 2)
    
    rect = patches.Rectangle((rect_left, rect_bottom), fov_w_mm, fov_h_mm,
                             linewidth=2, edgecolor='blue', facecolor='skyblue', alpha=0.1, label='FOV Window')
    ax.add_patch(rect)
    ax.text(rect_left + 10, rect_bottom + fov_h_mm - 20, "FOV Window", color='blue', fontsize=8)
    
    # Tee
    ax.plot(0, 0, 'kx', markersize=12, markeredgewidth=2)
    ax.text(0, -15, "Tee", ha='center', va='top', fontsize=8)
    
    # Ground
    ax.axhline(0, color='gray', linestyle='-', alpha=0.5)
    
    # Balls
    for i in range(num_pos):
        h_pos = first_pos + (i * spacing)
        
        # 1. Max VLA (Top)
        h_max = BALL_RADIUS_MM + (h_pos * math.tan(max_v_rad))
        ball_max = patches.Circle((h_pos, h_max), BALL_RADIUS_MM, facecolor='orange', edgecolor='black', linewidth=0.5, alpha=0.8)
        ax.add_patch(ball_max)
        ax.text(h_pos, h_max + 25, f"{start_num + i}", ha='center', fontsize=8, color='darkred')

        # 2. Min VLA (Bottom)
        h_min = BALL_RADIUS_MM + (h_pos * math.tan(min_v_rad))
        ball_min = patches.Circle((h_pos, h_min), BALL_RADIUS_MM, facecolor='orange', edgecolor='black', linewidth=0.5, alpha=0.8)
        ax.add_patch(ball_min)
        ax.text(h_pos, h_min - 35, f"{start_num + i}", ha='center', fontsize=8, color='darkgreen')

    ax.set_title(title + " (Camera View - YZ)")
    ax.set_xlabel("Horizontal Position from Tee (mm)")
    ax.set_ylabel("Vertical Height from Floor (mm)")
    
    # Apply Unified Limits
    if fixed_xlims: ax.set_xlim(fixed_xlims)
    if fixed_ylims: ax.set_ylim(fixed_ylims)
    
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle=':', alpha=0.6)
    
    return fig

# --- UI SETUP ---
st.title("📷 SimCam Optics Calculator")

# --- HELP SECTION ---
with st.sidebar.expander("❓ How to Use this Calculator"):
    st.markdown("""
    **1. Configure Targets**
    * Set your goals for Resolution, Brightness, and Geometry.
    
    **2. Set Hardware**
    * Choose a Lens and Aperture.
    
    **3. Fine Tune**
    * **Focus Offset:** Shifts focus.
    * **Vertical Offset:** Moves camera up/down.
    
    **4. Analyze Results**
    * **Green Rows:** Improvement.
    * **Top View:** Horizontal Tracking.
    * **LM View:** What the camera sees.
    """)

# Sidebar
st.sidebar.header("Sensor Config")
sensor_name = st.sidebar.selectbox("Select Sensor", list(SENSORS.keys()), help=sensor_help_text)
sensor = SENSORS[sensor_name]

use_binning = st.sidebar.checkbox("Enable 2x2 Binning", value=False, help="Combines 4 pixels into 1.")

st.sidebar.divider()
st.sidebar.subheader("Optimization Targets")
target_res = st.sidebar.number_input("Min Resolution (px/mm)", value=4.0, step=0.1)
target_bright = st.sidebar.number_input("Min Brightness (%)", value=80.0, step=10.0)
target_min_dist = st.sidebar.number_input("Min Distance (mm)", value=254, min_value=100, max_value=1000, step=10)
target_min_vla = st.sidebar.number_input("Min Vert Launch Angle (deg)", value=0.0, step=1.0)

coc_mult = st.sidebar.slider("Circle of Confusion (px)", 1.0, 3.0, 2.0, 0.1)

st.sidebar.divider()
st.sidebar.header("Ball Data")
include_club = st.sidebar.checkbox("Include Club Data", value=False)
num_pos = st.sidebar.number_input("Number of Positions", min_value=2, value=2, step=1)
first_pos = st.sidebar.number_input("First Image Position (mm)", value=152.4, step=10.0)
spacing = st.sidebar.number_input("Position Spacing (mm)", value=64.0, step=1.0)
st.sidebar.caption(f"Ref: Golf Ball Dia = {BALL_DIAMETER_MM} mm")

# --- STATE ---
if 'focal' not in st.session_state: st.session_state.focal = 6.0
if 'aperture' not in st.session_state: st.session_state.aperture = 1.2
if 'distance' not in st.session_state: st.session_state.distance = 430
if 'focus_offset' not in st.session_state: st.session_state.focus_offset = 0
if 'cam_z' not in st.session_state: st.session_state.cam_z = 0

# --- AUTO OPTIMIZER ---
st.markdown("### 🚀 Auto-Optimizer")
if st.button("✨ Optimize System (Max DOF > Max Dist)"):
    valid_configs = []
    bin_factor = 2 if use_binning else 1
    px_mm = (sensor["pixel_size"] * bin_factor) / 1000
    
    for f in REAL_FOCAL_LENGTHS:
        for aper in REAL_APERTURES:
            max_res_dist = int(f / (px_mm * target_res))
            if max_res_dist > 1000: max_res_dist = 1000
            if max_res_dist < target_min_dist: continue
            
            found_d_for_lens = None
            for d in range(max_res_dist, target_min_dist - 1, -20):
                base_chk = calculate_metrics(sensor, use_binning, 810, f, aper, d, 
                                           include_club, num_pos, first_pos, spacing, 0, coc_mult, 0, None, True)
                if base_chk['bright'] >= target_bright:
                    found_d_for_lens = d
                    break 
            
            if found_d_for_lens:
                # 1. Focus
                best_off_local = 0
                best_diff = 9999
                for off in range(-400, 200, 10):
                    m = calculate_metrics(sensor, use_binning, 810, f, aper, found_d_for_lens, 
                                        include_club, num_pos, first_pos, spacing, off, coc_mult, 0, None, True)
                    near = m['near_limit']
                    far = m['far_limit']
                    if far > 99999: diff = 0 
                    else: diff = abs((found_d_for_lens - near) - (far - found_d_for_lens))
                    if diff < best_diff:
                        best_diff = diff
                        best_off_local = off
                
                # 2. Cam Z
                flight_d = first_pos + (num_pos - 1) * spacing
                offset_needed = math.tan(math.radians(target_min_vla)) * flight_d
                optimal_cam_z_offset = offset_needed
                
                final_m = calculate_metrics(sensor, use_binning, 810, f, aper, found_d_for_lens, 
                                          include_club, num_pos, first_pos, spacing, best_off_local, coc_mult, optimal_cam_z_offset, None, True)
                
                valid_configs.append({
                    "f": f, "aper": aper, "dist": found_d_for_lens, 
                    "offset": best_off_local, "cam_z": optimal_cam_z_offset,
                    "dof": final_m['dof']
                })
    
    if valid_configs:
        valid_configs.sort(key=lambda x: (x['dof'], x['dist']), reverse=True)
        winner = valid_configs[0]
        st.session_state.focal = winner['f']
        st.session_state.aperture = winner['aper']
        st.session_state.distance = winner['dist']
        st.session_state.focus_offset = winner['offset']
        st.session_state.cam_z = winner['cam_z']
        st.success(f"🏆 Found: {winner['f']}mm @ f/{winner['aper']} (Dist: {winner['dist']}mm)")
        st.rerun()
    else:
        st.error("❌ No configuration found satisfying Targets.")

st.divider()

# --- MANUAL INPUTS ---
r1_c1, r1_c2, r1_c3 = st.columns(3)

with r1_c1: 
    st.session_state.focal = st.select_slider("Focal (mm)", REAL_FOCAL_LENGTHS, st.session_state.focal)
    if st.button("Optimize Lens Only"):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        ideal_f = st.session_state.distance * px_mm * target_res
        st.session_state.focal = find_nearest(REAL_FOCAL_LENGTHS, ideal_f)
        st.rerun()
        
with r1_c2: 
    st.session_state.aperture = st.select_slider("Aperture (f/)", REAL_APERTURES, st.session_state.aperture)
    if st.button("Optimize f-stop Only"):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        qe = sensor["qe"].get(810, 0.2)
        base_px_area = BASE_PARAMS["sensor"]["pixel_size"] ** 2
        base_score = (BASE_PARAMS["sensor"]["qe"][810] * base_px_area) / ((BASE_PARAMS["aperture"]**2) * (BASE_PARAMS["distance"]**2))
        target_score = (target_bright / 100) * base_score
        f_sq = (qe * (px_size_um := sensor["pixel_size"] * bin_factor)**2) / (target_score * st.session_state.distance**2)
        max_f = math.sqrt(f_sq)
        valid = [x for x in REAL_APERTURES if x <= max_f]
        if valid: st.session_state.aperture = max(valid) 
        else: st.session_state.aperture = 1.2 
        st.rerun()

with r1_c3: 
    st.session_state.distance = st.slider("Distance (mm)", 100, 1000, st.session_state.distance, 1)
    if st.button("Optimize Dist Only"):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        max_res_dist = int(st.session_state.focal / (px_mm * target_res))
        
        best_d = None
        start_d = min(max_res_dist, 1000)
        
        for d in range(start_d, 100, -10): 
             # Use current focus offset (no optimization)
             base_chk = calculate_metrics(sensor, use_binning, 810, st.session_state.focal, st.session_state.aperture, d,
                                    include_club, num_pos, first_pos, spacing, st.session_state.focus_offset, coc_mult, 0, None, True)
             if base_chk['bright'] >= target_bright:
                 best_d = d
                 break 
        
        if best_d and best_d >= target_min_dist:
            st.session_state.distance = best_d
            st.rerun()
        else:
            st.error("Cannot satisfy constraints.")

# Bottom Row: Adjustments (2 cols)
r2_c1, r2_c2 = st.columns(2)

with r2_c1:
    focus_offset = st.slider("Focus Offset (mm)", -400, 200, st.session_state.focus_offset, 5)
    if st.button("Optimize Focus Only"):
        best_off = 0
        best_diff = 9999
        for off in range(-400, 200, 5):
            m = calculate_metrics(sensor, use_binning, 810, st.session_state.focal, st.session_state.aperture, st.session_state.distance,
                                include_club, num_pos, first_pos, spacing, off, coc_mult, 0, None, True)
            near = m['near_limit']
            far = m['far_limit']
            if far > 99999: diff = 0 
            else: diff = abs((st.session_state.distance - near) - (far - st.session_state.distance))
            if diff < best_diff:
                best_diff = diff
                best_off = off
        st.session_state.focus_offset = best_off
        st.rerun()

with r2_c2:
    cam_z = st.slider("Vertical Camera Offset (mm)", -500, 500, int(st.session_state.cam_z), 5)
    
    if st.button("Optimize Vert Cam Only"):
        flight_d = first_pos + (num_pos - 1) * spacing
        offset_needed = math.tan(math.radians(target_min_vla)) * flight_d
        st.session_state.cam_z = int(offset_needed)
        st.rerun()


# --- RESULTS ---
vals = calculate_metrics(sensor, use_binning, 810, st.session_state.focal, st.session_state.aperture, st.session_state.distance,
                        include_club, num_pos, first_pos, spacing, st.session_state.focus_offset, coc_mult, st.session_state.cam_z, None, False)

# --- BASELINE ---
base_fov_h = (BASE_PARAMS["sensor"]["height_px"] * BASE_PARAMS["sensor"]["pixel_size"] / 1000 * BASE_PARAMS["distance"]) / BASE_PARAMS["focal"]
base_fov_w = (BASE_PARAMS["sensor"]["width_px"] * BASE_PARAMS["sensor"]["pixel_size"] / 1000 * BASE_PARAMS["distance"]) / BASE_PARAMS["focal"]
base_offset = BASE_PARAMS["height_target"] - (base_fov_h / 2)
# Baseline start: 530 + 1inch - FOV/2
baseline_first_pos = 530 + 25.4 - (base_fov_w / 2)

base_res = calculate_metrics(
    BASE_PARAMS["sensor"], BASE_PARAMS["binning"], BASE_PARAMS["wavelength"], 
    BASE_PARAMS["focal"], BASE_PARAMS["aperture"], BASE_PARAMS["distance"],
    False, num_pos, baseline_first_pos, spacing, 0, coc_mult, base_offset, BASE_PARAMS["y_pos"], False 
)

# --- TABLE ---
def fmt_mm_in(val): return f"{val:.1f} mm ({val/25.4:.1f}\")"
def fmt_dof(dof, dn, df): 
    return f"{dof:.1f} mm [{int(dn)} - {int(df)}]"
def fmt_angle(min_val, max_val):
    if min_val is None: return "NOT POSSIBLE"
    return f"[{min_val:+.1f}°, {max_val:+.1f}°]"

metrics = [
    ("Lens", 
     f"{BASE_PARAMS['focal']:.1f}mm f/{BASE_PARAMS['aperture']:.1f}", 
     f"{st.session_state.focal:.1f}mm f/{st.session_state.aperture:.1f}", 
     "", False),
    ("Distance", BASE_PARAMS["distance"], st.session_state.distance, "mm", False),
    ("Camera Height", base_res['total_cam_height'], vals['total_cam_height'], " mm", False),
    ("FOV Width", base_res['fov_w'], vals['fov_w'], " mm", True),
    ("FOV Height", base_res['fov_h'], vals['fov_h'], " mm", True),
    ("Resolution", base_res['res'], vals['res'], " px/mm", True),
    ("Brightness", 100.0, vals['bright'], "%", True),
    ("Focus Zone", 
     (base_res['dof'], base_res['near_limit'], base_res['far_limit']), 
     (vals['dof'], vals['near_limit'], vals['far_limit']), "dof_complex", True),
    ("Horiz Launch Angle", (base_res['min_h_angle'], base_res['max_h_angle']), (vals['min_h_angle'], vals['max_h_angle']), "angle_complex", True),
    ("Vert Launch Angle", (base_res['min_v_angle'], base_res['max_v_angle']), (vals['min_v_angle'], vals['max_v_angle']), "angle_complex", True),
]

data = []
for name, base, new_val, unit, diff in metrics:
    row = {
        "Metric": name,
        "Baseline": "",
        "Your Setup": "",
        "Change": "",
        "status": "neutral"
    }
    
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
    elif unit == "angle_complex":
        b_min, b_max = base
        n_min, n_max = new_val
        if b_min is None or n_min is None:
            row["Baseline"] = "N/A"
            row["Your Setup"] = "NOT POSSIBLE"
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
    elif unit == "": 
        row["Baseline"] = base
        row["Your Setup"] = new_val
        row["Change"] = "" 
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
display_cols = ["Metric", "Baseline", "Your Setup", "Change"]

def style_fn(styler):
    def color_rows(row):
        c = ''
        if row['status'] in ['pass','good']: c = 'background-color: rgba(144, 238, 144, 0.3)'
        elif row['status'] in ['fail','bad']: c = 'background-color: rgba(255, 99, 71, 0.3)'
        return [c] * len(row)
    return styler.apply(color_rows, axis=1)

st.markdown("### 📊 Performance")
st.dataframe(style_fn(df.style), width="stretch", hide_index=True, column_order=display_cols)

# --- SCHEMATICS ---
st.markdown("### 📐 Top-Down Schematic")
sch_c1, sch_c2 = st.columns(2)

x_max = max(BASE_PARAMS["distance"], st.session_state.distance) + 250
balls_max_y = first_pos + (num_pos * spacing) + 100
fov_max_y = max(base_res["fov_top"], vals["fov_top"]) + 50
fov_min_y = min(base_res["fov_bottom"], vals["fov_bottom"]) - 50
y_limits = (fov_min_y, max(balls_max_y, fov_max_y))

with sch_c1:
    fig1 = plot_schematic("Baseline", BASE_PARAMS["distance"], base_res["fov_w"], 
                         base_res["fov_center"], base_res["near_limit"], base_res["far_limit"],
                         False, num_pos, baseline_first_pos, spacing, x_max, y_limits, BASE_PARAMS["distance"],
                         base_res['safe_near_dev'], base_res['safe_far_dev'], base_res['flight_dist'])
    st.pyplot(fig1)

with sch_c2:
    fig2 = plot_schematic("Your Setup", st.session_state.distance, vals["fov_w"], 
                         vals["fov_center"], vals["near_limit"], vals["far_limit"],
                         include_club, num_pos, first_pos, spacing, x_max, y_limits, vals["focus_dist"],
                         vals['safe_near_dev'], vals['safe_far_dev'], vals['flight_dist'])
    st.pyplot(fig2)

st.markdown("### 📐 LM View (YZ - Camera Perspective)")
lm_c1, lm_c2 = st.columns(2)

# Global Limits for Unified Scale
# X axis covers FOV width
# Ensure min x includes the Tee (0) with some margin (-50)
base_left = base_res["fov_center"] - base_res["fov_w"]/2
vals_left = vals["fov_center"] - vals["fov_w"]/2
all_min_x = min(base_left, vals_left, -50) - 20 

all_max_x = max(base_res["fov_center"] + base_res["fov_w"]/2, vals["fov_center"] + vals["fov_w"]/2) + 50
# Y axis covers Height + FOV/2
all_max_y = max(base_res["total_cam_height"] + base_res["fov_h"]/2, vals["total_cam_height"] + vals["fov_h"]/2) + 50

with lm_c1:
    fig3 = plot_sensor_view_final("Baseline", base_res["fov_w"], 
                          base_res["fov_h"], base_res["fov_center"], base_res["total_cam_height"], 
                          base_res["min_v_rad"], base_res["max_v_rad"], 
                          num_pos, baseline_first_pos, spacing, 1,
                          (all_min_x, all_max_x), (-50, all_max_y))
    st.pyplot(fig3)

with lm_c2:
    start_n = 3 if include_club else 1
    fig4 = plot_sensor_view_final("Your Setup", vals["fov_w"], 
                          vals["fov_h"], vals["fov_center"], vals["total_cam_height"], 
                          vals["min_v_rad"], vals["max_v_rad"], 
                          num_pos, first_pos, spacing, start_n,
                          (all_min_x, all_max_x), (-50, all_max_y))
    st.pyplot(fig4)