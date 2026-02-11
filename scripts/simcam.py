import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as mlines

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
                      coc_mult, cam_z_offset, fixed_y_center=None, ignore_ball_fit=False,
                      is_stereo=False, stereo_base=0, stereo_align="Horizontal"):
    
    bin_factor = 2 if binning else 1
    px_size_um = sensor["pixel_size"] * bin_factor
    px_size_mm = px_size_um / 1000.0
    width_px = sensor["width_px"] / bin_factor
    height_px = sensor["height_px"] / bin_factor
    sensor_w = width_px * px_size_mm
    sensor_h = height_px * px_size_mm
    
    # Raw FOV at Distance D
    raw_fov_w = (sensor_w * dist) / focal
    raw_fov_h = (sensor_h * dist) / focal
    
    # Effective Overlap FOV
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
    
    # FOV Position
    if fixed_y_center is not None:
        fov_center = fixed_y_center
    else:
        # Default Baseline Logic (Only used for baseline calculation, not sliders)
        if include_club:
            fov_bottom = -152.4
            fov_center = fov_bottom + (eff_fov_w / 2)
        else:
            fov_bottom = first_pos - 25.4
            fov_center = fov_bottom + (eff_fov_w / 2)
            
    fov_top = fov_center + (eff_fov_w / 2)
    fov_bottom = fov_center - (eff_fov_w / 2)
    
    # Camera Height
    base_cam_height = raw_fov_h / 2 
    total_cam_height = base_cam_height + cam_z_offset
    
    res = width_px / raw_fov_w
    
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
    
    # --- VALIDITY CHECK (Are balls in FOV?) ---
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
         safe_far = 9999
    else:
         safe_far = max(0, df - dist)
         max_h_angle = math.degrees(math.atan(safe_far / flight_dist))
    
    # --- VERTICAL ANGLES ---
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
        min_h_angle = None
        max_h_angle = None
        min_v_angle = None 
        max_v_angle = None

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

# --- PLOTTING FUNCTION (TOP DOWN) ---
def plot_schematic(title, dist_mm, vals, num_pos, first_pos, spacing, x_limits, y_limits, include_club):
    
    fig, ax = plt.subplots(figsize=(5, 5), dpi=120) 
    
    fov_center_y = vals["fov_center"]
    fov_w_mm = vals["fov_w"]
    raw_w = vals["raw_fov_w"]
    
    cam_centers = []
    is_stereo = vals["stereo_base"] > 0
    if is_stereo and vals["stereo_align"] == "Horizontal":
        offset = vals["stereo_base"] / 2
        cam_centers = [(0, fov_center_y - offset), (0, fov_center_y + offset)]
    else:
        cam_centers = [(0, fov_center_y)]

    # Draw Single LM Body (Centered)
    lm_rect = patches.Rectangle((-150, fov_center_y - 75), 150, 150, 
                               linewidth=1, edgecolor='black', facecolor='#222222', alpha=0.9, zorder=20)
    ax.add_patch(lm_rect)
    ax.text(-75, fov_center_y, "LM", ha='center', va='center', color='white', fontweight='bold', zorder=21)

    # Draw Cameras
    for cx, cy in cam_centers:
        raw_top = cy + (raw_w / 2)
        raw_bot = cy - (raw_w / 2)
        if is_stereo:
            ax.plot([0, dist_mm], [cy, raw_top], color='gray', linestyle=':', alpha=0.3, zorder=1)
            ax.plot([0, dist_mm], [cy, raw_bot], color='gray', linestyle=':', alpha=0.3, zorder=1)
        else:
            ax.plot([0, dist_mm], [cy, raw_top], color='skyblue', linestyle='--', alpha=0.3, zorder=1)
            ax.plot([0, dist_mm], [cy, raw_bot], color='skyblue', linestyle='--', alpha=0.3, zorder=1)

    # Overlap
    fov_top = fov_center_y + (fov_w_mm / 2)
    fov_bottom = fov_center_y - (fov_w_mm / 2)
    label_fov = 'Overlap FOV' if is_stereo else 'FOV'
    ax.fill([0, dist_mm, dist_mm], [fov_center_y, fov_top, fov_bottom], alpha=0.2, color='blue', label=label_fov, zorder=2)
    
    # DOF
    dof_near = vals["near_limit"]
    dof_far = vals["far_limit"]
    plot_far = min(dof_far, dist_mm + 500)
    dof_rect = patches.Rectangle((dof_near, fov_bottom), plot_far - dof_near, fov_w_mm, 
                                 linewidth=1, edgecolor='green', facecolor='green', alpha=0.15, zorder=3, label="Focus Zone")
    ax.add_patch(dof_rect)
    
    # Tee
    ax.axvline(dist_mm, color='red', linestyle=':', alpha=0.5, zorder=4)
    ax.plot(dist_mm, 0, 'kx', markersize=8, markeredgewidth=2, zorder=5)
    ax.text(dist_mm, -20, "Tee", ha='center', va='top', fontweight='bold', zorder=20)
    
    lbl_off = 35 
    
    # CLUB DATA
    start_num = 1
    if include_club:
        club_y_min = -101.6 
        club_y_max = 25.4   
        cx_min = dof_near
        cx_max = min(dof_far, x_limits[1] + 100)
        ax.plot([cx_min, cx_max], [club_y_min, club_y_min], color='red', linestyle=':', linewidth=1.5, zorder=4)
        ax.text(dist_mm + lbl_off, club_y_min, "1", color='blue', fontweight='bold', va='center', zorder=20)
        ax.plot([cx_min, cx_max], [club_y_max, club_y_max], color='red', linestyle=':', linewidth=1.5, zorder=4)
        ax.text(dist_mm + lbl_off, club_y_max, "2", color='blue', fontweight='bold', va='center', zorder=20)
        start_num = 3
    
    # BALLS & GHOSTS
    safe_near_dev = vals["safe_near_dev"]
    safe_far_dev = vals["safe_far_dev"]
    flight_dist = vals["flight_dist"]
    
    # Legend Handles
    real_ball_handle = mlines.Line2D([], [], color='red', marker='o', linestyle='None', markersize=8, label='Straight Shot')
    # Ghost Ball Handle (Solid Line Open Circle for Ghost)
    ghost_ball_handle = mlines.Line2D([], [], color='red', marker='o', linestyle='None', 
                                      markersize=8, markerfacecolor='none', markeredgewidth=1.5, label='Min/Max HLA')
    
    for i in range(num_pos):
        y = first_pos + (i * spacing)
        # Real
        ax.add_patch(patches.Circle((dist_mm, y), BALL_RADIUS_MM, facecolor='red', edgecolor='black', linewidth=0.5, zorder=10))
        
        # Ghost (HLA)
        if flight_dist > 0: scale = y / flight_dist
        else: scale = 0
        
        near_offset = safe_near_dev * scale
        far_offset = safe_far_dev * scale
        
        ax.add_patch(patches.Circle((dist_mm - near_offset, y), BALL_RADIUS_MM, linestyle='-', linewidth=1.5, edgecolor='red', facecolor='none', zorder=11))
        
        label_x = dist_mm + 40
        if safe_far_dev < 9000:
            ax.add_patch(patches.Circle((dist_mm + far_offset, y), BALL_RADIUS_MM, linestyle='-', linewidth=1.5, edgecolor='red', facecolor='none', zorder=11))
            label_x = dist_mm + far_offset + 30
            
        ax.text(label_x, y, str(start_num + i), color='black', fontweight='bold', va='center', zorder=20)
    
    # Arrow
    arrow_x = x_limits[1] - 50
    ax.arrow(arrow_x, 0, 0, 200, head_width=20, head_length=40, fc='k', ec='k', zorder=5)
    ax.text(arrow_x + 30, 100, "Swing Direction", rotation=90, va='center', zorder=5)

    ax.set_title(title + " (Top View)")
    ax.set_xlabel("Distance Perpendicular (mm)")
    ax.set_ylabel("Distance Parallel (mm)")
    
    ax.set_xlim(x_limits)
    ax.set_ylim(y_limits)
    
    ax.set_aspect('equal', adjustable='box') 
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Custom Legend
    handles, labels = ax.get_legend_handles_labels()
    handles.extend([real_ball_handle, ghost_ball_handle])
    
    if is_stereo:
        left_h = mlines.Line2D([], [], color='red', linestyle=':', label='Left/Bot Cam FOV')
        right_h = mlines.Line2D([], [], color='green', linestyle=':', label='Right/Top Cam FOV')
        handles.extend([left_h, right_h])
        
    ax.legend(handles=handles, loc='best', fontsize='small', framealpha=0.9)
    
    return fig

# --- PLOTTING FUNCTION (YZ SENSOR VIEW) ---
def plot_sensor_view_final(title, vals, num_pos, first_pos, spacing, start_num, fixed_xlims=None, fixed_ylims=None, include_club=False):
                     
    fig, ax = plt.subplots(figsize=(5, 5), dpi=120)
    
    fov_center_x = vals["fov_center"]
    
    eff_bottom = vals["fov_bottom_z_near"] 
    eff_top = min(vals["fov_top_z_far"], 3000)
    eff_height = eff_top - eff_bottom
    eff_width = vals["fov_w"]
    rect_left = fov_center_x - (eff_width / 2)
    cam_height = vals["total_cam_height"]
    
    is_stereo = vals["stereo_base"] > 0
    label_fov = 'Overlap FOV' if is_stereo else 'FOV'
    
    # Draw Club Data Lines (Vertical dotted red)
    if include_club:
        club_x_1 = -101.6
        club_x_2 = 25.4
        
        # Line 1
        ax.vlines(club_x_1, eff_bottom, eff_bottom + eff_height, colors='red', linestyles=':', linewidth=1.5, zorder=5)
        ax.text(club_x_1, eff_bottom + eff_height + 10, "1", color='blue', fontweight='bold', ha='center', fontsize=10)
        
        # Line 2
        ax.vlines(club_x_2, eff_bottom, eff_bottom + eff_height, colors='red', linestyles=':', linewidth=1.5, zorder=5)
        ax.text(club_x_2, eff_bottom + eff_height + 10, "2", color='blue', fontweight='bold', ha='center', fontsize=10)

    # Draw Individual Camera Frames (Dotted)
    if is_stereo:
        base = vals["stereo_base"]
        raw_w = vals["raw_fov_w"]
        
        if vals["stereo_align"] == "Horizontal":
            c1_x = fov_center_x - (base/2)
            c2_x = fov_center_x + (base/2)
            rect1 = patches.Rectangle((c1_x - raw_w/2, eff_bottom), raw_w, eff_height, linewidth=1, edgecolor='red', linestyle='--', facecolor='none', label='Left Cam')
            rect2 = patches.Rectangle((c2_x - raw_w/2, eff_bottom), raw_w, eff_height, linewidth=1, edgecolor='green', linestyle='--', facecolor='none', label='Right Cam')
            ax.add_patch(rect1)
            ax.add_patch(rect2)
        else: # Vertical
            rect1 = patches.Rectangle((rect_left, eff_bottom - (base/2)), eff_width, eff_height + base, linewidth=1, edgecolor='red', linestyle='--', facecolor='none', label='Bot Cam')
            rect2 = patches.Rectangle((rect_left, eff_bottom + (base/2)), eff_width, eff_height + base, linewidth=1, edgecolor='green', linestyle='--', facecolor='none', label='Top Cam')
            ax.add_patch(rect1)
            ax.add_patch(rect2)

    # Effective Window
    rect = patches.Rectangle((rect_left, eff_bottom), eff_width, eff_height,
                             linewidth=2, edgecolor='blue', facecolor='skyblue', alpha=0.1, label=label_fov)
    ax.add_patch(rect)
    
    # Tee
    ax.plot(0, 0, 'kx', markersize=12, markeredgewidth=2)
    ax.text(0, -15, "Tee", ha='center', va='top', fontsize=8)
    ax.axhline(0, color='gray', linestyle='-', alpha=0.5)
    
    min_rad = vals["min_v_rad"]
    max_rad = vals["max_v_rad"]
    
    for i in range(num_pos):
        h_pos = first_pos + (i * spacing)
        
        h_max = BALL_RADIUS_MM + (h_pos * math.tan(max_rad))
        # Removed label= here to prevent Rectangle creation
        ball_max = patches.Circle((h_pos, h_max), BALL_RADIUS_MM, facecolor='orange', edgecolor='black', linewidth=0.5, alpha=0.8)
        ax.add_patch(ball_max)
        ax.text(h_pos, h_max + 25, f"{start_num + i}", ha='center', fontsize=8, color='darkred')

        h_min = BALL_RADIUS_MM + (h_pos * math.tan(min_rad))
        ball_min = patches.Circle((h_pos, h_min), BALL_RADIUS_MM, facecolor='orange', edgecolor='black', linewidth=0.5, alpha=0.8)
        ax.add_patch(ball_min)
        ax.text(h_pos, h_min - 35, f"{start_num + i}", ha='center', fontsize=8, color='darkgreen')

    ax.set_title(title + " (Camera View - YZ)")
    ax.set_xlabel("Horiz (mm)")
    ax.set_ylabel("Vert (mm)")
    
    if fixed_xlims: ax.set_xlim(fixed_xlims)
    if fixed_ylims: ax.set_ylim(fixed_ylims)
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Manual VLA Handle (Circle)
    vla_handle = mlines.Line2D([], [], color='orange', marker='o', linestyle='None', markeredgecolor='black', markersize=8, alpha=0.8, label='Min/Max VLA')
    
    handles, labels = ax.get_legend_handles_labels()
    # Replace/Append custom handles
    final_handles = []
    final_labels = []
    
    # Add Camera handles from plot
    for h, l in zip(handles, labels):
        final_handles.append(h)
        final_labels.append(l)
    
    # Add VLA handle explicitly
    final_handles.append(vla_handle)
    final_labels.append("Min/Max VLA")
    
    ax.legend(final_handles, final_labels, loc='best', fontsize='small', framealpha=0.9)
    
    return fig

# --- UI SETUP ---
st.title("📷 SimCam Optics Calculator")

# --- HELP SECTION ---
with st.sidebar.expander("❓ How to Use this Calculator"):
    st.markdown("""
    ### **Step 1: Set Optimization Targets**
    * **Resolution:** Minimum sharpness (pixels per mm) required on the ball.
    * **Brightness:** Relative brightness compared to the baseline setup.
    * **Min Distance:** Closest physical distance you can place the camera (safety).
    * **Min VLA:** Launch angle needed to see the floor (0 deg = Floor Visible).

    ### **Step 2: Select Hardware**
    * **Sensor:** Choose from the dropdown list.
    * **Stereoscopic Mode:**
        * **Checked:** Calculates overlap for dual cameras.
        * **Ratio:** 1:5 is industry standard. 1:30 is wider overlap but less depth precision.

    ### **Step 3: Geometry & Positioning**
    * **Distance Perpendicular:** How far back the camera is (X-axis).
    * **Distance Parallel:** Where the camera centers horizontally (Y-axis).
        * *Auto-calculated to center 1 inch below the first ball.*
        * *If Club Data is ON, centers at -5 inches.*

    ### **Step 4: Analyze the Plots**
    * **Top View:** Look at the **"Blue Zone"**.
        * The Red Ball must be inside it.
        * The **"Ghost Balls"** (Red Circles) show where a ball might appear if it drifts left/right (HLA).
    * **Camera View (YZ):**
        * Shows the vertical window.
        * **Orange Balls** represent the maximum Vertical Launch Angle (VLA) fit.
        * **Blue Numbers (1, 2)** indicate club tracking lines if enabled.
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
target_bright = st.sidebar.number_input("Min Brightness (%)", value=80.0, step=10.0, help="Minimum relative brightness compared to the baseline setup.")
target_min_dist = st.sidebar.number_input("Min Distance (mm)", value=254, min_value=100, max_value=1000, step=10, help="Closest allowed physical distance from Camera to Tee.")
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
first_pos = st.sidebar.number_input("First Image Position (mm)", value=152.4, step=10.0, help="Distance from Tee to the FIRST ball image.")
spacing = st.sidebar.number_input("Position Spacing (mm)", value=64.0, step=1.0, help="Distance between sequential ball images.")
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
st.markdown("### 🚀 Auto-Optimizer")
if st.button("✨ Optimize System", help="Iterates through all lens/aperture combinations. Prioritizes maximizing Depth of Field (Focus Zone) first, then maximizes Perpendicular Distance."):
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
                trial_base = int(d / stereo_ratio) if is_stereo else 0
                
                # Dynamic Parallel Opt
                sensor_w_inner = (sensor["width_px"] / bin_factor) * px_mm
                eff_fov_w_inner = (sensor_w_inner * d) / f
                if is_stereo and stereo_align == "Horizontal":
                    eff_fov_w_inner = max(0, eff_fov_w_inner - trial_base)
                
                if include_club:
                    opt_parallel = -127.0 + (eff_fov_w_inner / 2)
                else:
                    opt_parallel = (first_pos - 25.4) + (eff_fov_w_inner / 2)
                
                chk = calculate_metrics(sensor, use_binning, 810, f, aper, d, 
                                       include_club, num_pos, first_pos, spacing, 0, coc_mult, 0, opt_parallel, True,
                                       is_stereo, trial_base, stereo_align)
                if chk['bright'] >= target_bright:
                    found_d_for_lens = d
                    found_parallel_for_lens = opt_parallel
                    break 
            
            if found_d_for_lens:
                trial_base = int(found_d_for_lens / stereo_ratio) if is_stereo else 0
                best_off = 0
                best_diff = 9999
                for off in range(-400, 200, 10):
                    m = calculate_metrics(sensor, use_binning, 810, f, aper, found_d_for_lens, 
                                        include_club, num_pos, first_pos, spacing, off, coc_mult, 0, found_parallel_for_lens, True,
                                        is_stereo, trial_base, stereo_align)
                    near = m['near_limit']
                    far = m['far_limit']
                    if far > 99999: diff = 0 
                    else: diff = abs((found_d_for_lens - near) - (far - found_d_for_lens))
                    if diff < best_diff:
                        best_diff = diff
                        best_off = off
                
                flight_d = first_pos + (num_pos - 1) * spacing
                m_z0 = calculate_metrics(sensor, use_binning, 810, f, aper, found_d_for_lens, 
                                        include_club, num_pos, first_pos, spacing, best_off, coc_mult, 0, found_parallel_for_lens, True,
                                        is_stereo, trial_base, stereo_align)
                
                current_min_v = m_z0['min_v_angle']
                deg_diff = current_min_v - target_min_vla
                drop_mm = math.tan(math.radians(deg_diff)) * flight_d
                optimal_cam_z = int(0 - drop_mm)
                
                final_m = calculate_metrics(sensor, use_binning, 810, f, aper, found_d_for_lens, 
                                          include_club, num_pos, first_pos, spacing, best_off, coc_mult, optimal_cam_z, found_parallel_for_lens, True,
                                          is_stereo, trial_base, stereo_align)
                
                if final_m['min_h_angle'] is not None and final_m['min_v_angle'] <= target_min_vla + 0.5:
                    valid_configs.append({
                        "f": f, "aper": aper, "dist": found_d_for_lens, 
                        "offset": best_off, "cam_z": optimal_cam_z,
                        "parallel": found_parallel_for_lens,
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
        st.session_state.dist_parallel = int(winner['parallel'])
        st.success(f"🏆 Found: {winner['f']}mm @ f/{winner['aper']} (Dist: {winner['dist']}mm)")
        st.rerun()
    else:
        st.error("❌ No configuration found satisfying Targets.")

st.divider()

# --- MANUAL INPUTS ---
c1, c2, c3 = st.columns(3)
with c1: 
    st.session_state.focal = st.select_slider("Focal (mm)", REAL_FOCAL_LENGTHS, st.session_state.focal, help="Lens Focal Length.")
    if st.button("Optimize Lens Only", help="Finds the best lens focal length for the current distance."):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        ideal_f = st.session_state.distance * px_mm * target_res
        st.session_state.focal = find_nearest(REAL_FOCAL_LENGTHS, ideal_f)
        st.rerun()
        
with c2: 
    st.session_state.aperture = st.select_slider("Aperture (f/)", REAL_APERTURES, st.session_state.aperture, help="Lens Aperture (Iris).")
    if st.button("Optimize f-stop Only", help="Finds the smallest aperture (highest f-number) that meets the brightness target."):
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

with c3: 
    st.session_state.distance = st.slider("Distance Perpendicular to Swing (mm)", 100, 1000, st.session_state.distance, 1, help="Horizontal distance from Lens to Tee.")
    if st.button("Optimize Dist Only", help="Finds the maximum distance that satisfies the Resolution and Brightness targets."):
        bin_factor = 2 if use_binning else 1
        px_mm = (sensor["pixel_size"] * bin_factor) / 1000
        max_res_dist = int(st.session_state.focal / (px_mm * target_res))
        
        best_d = None
        start_d = min(max_res_dist, 1000)
        
        for d in range(start_d, 100, -10): 
             # Use current focus offset (no optimization)
             trial_base = int(d / stereo_ratio) if is_stereo else 0
             base_chk = calculate_metrics(sensor, use_binning, 810, st.session_state.focal, st.session_state.aperture, d,
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

c4, c5, c6 = st.columns(3)
with c4: 
    st.session_state.focus_offset = st.slider("Focus Offset", -400, 200, st.session_state.focus_offset, 5, help="Shifts the focal plane closer (-) or further (+).")
    if st.button("Optimize Focus Only", help="Adjusts focus offset to center the Depth of Field around the Tee."):
        best_off = 0
        best_diff = 9999
        for off in range(-400, 200, 5):
            m = calculate_metrics(sensor, use_binning, 810, st.session_state.focal, st.session_state.aperture, st.session_state.distance,
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
    st.session_state.cam_z = st.slider("Vert Cam Offset", -500, 500, int(st.session_state.cam_z), 5, help="0 = Bottom of FOV aligns with Tee level (0°). Positive values raise the camera.")
    if st.button("Optimize Vert Cam Only", help="Adjusts vertical height to meet the Min Vert Launch Angle target."):
        flight_d = first_pos + (num_pos - 1) * spacing
        offset_needed = math.tan(math.radians(target_min_vla)) * flight_d
        st.session_state.cam_z = int(offset_needed)
        st.rerun()

with c6:
    st.session_state.dist_parallel = st.slider("Distance Parallel to Swing (mm)", -200, 600, int(st.session_state.dist_parallel), 1, help="Shift Camera Left/Right along the swing line.")
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
vals = calculate_metrics(sensor, use_binning, 810, st.session_state.focal, st.session_state.aperture, st.session_state.distance,
                        include_club, num_pos, first_pos, spacing, st.session_state.focus_offset, coc_mult, st.session_state.cam_z, st.session_state.dist_parallel, False,
                        is_stereo, stereo_base_val, stereo_align)

base_fov_h = (BASE_PARAMS["sensor"]["height_px"] * BASE_PARAMS["sensor"]["pixel_size"] / 1000 * BASE_PARAMS["distance"]) / BASE_PARAMS["focal"]
base_fov_w = (BASE_PARAMS["sensor"]["width_px"] * BASE_PARAMS["sensor"]["pixel_size"] / 1000 * BASE_PARAMS["distance"]) / BASE_PARAMS["focal"]
base_offset = BASE_PARAMS["height_target"] - (base_fov_h / 2)
baseline_first_pos = 530 + 25.4 - (base_fov_w / 2)

base_res = calculate_metrics(
    BASE_PARAMS["sensor"], BASE_PARAMS["binning"], BASE_PARAMS["wavelength"], 
    BASE_PARAMS["focal"], BASE_PARAMS["aperture"], BASE_PARAMS["distance"],
    False, num_pos, baseline_first_pos, spacing, 0, coc_mult, base_offset, BASE_PARAMS["y_pos"], False,
    False, 0, "Horizontal"
)

# --- RESULTS TABLE ---
def fmt_dof(dof, dn, df): return f"{dof:.1f} mm [{int(dn)} - {int(df)}]"
def fmt_angle(min_val, max_val):
    if min_val is None: return "NOT VISIBLE"
    return f"[{min_val:+.1f}°, {max_val:+.1f}°]"

metrics = [
    ("Lens", f"{BASE_PARAMS['focal']}mm f/{BASE_PARAMS['aperture']}", f"{st.session_state.focal}mm f/{st.session_state.aperture}", "", False),
    ("Distance Perpendicular", BASE_PARAMS["distance"], st.session_state.distance, "mm", False),
    ("Distance Parallel (Center)", BASE_PARAMS["y_pos"], st.session_state.dist_parallel, "mm", False),
]

if is_stereo:
    metrics.append(("Stereo Base (Camera Separation)", "N/A", f"{stereo_base_val}mm", "", False))

metrics.extend([
    ("Camera Height", base_res['total_cam_height'], vals['total_cam_height'], " mm", False),
    ("FOV Width" if not is_stereo else "FOV Width (Overlap)", base_res['fov_w'], vals['fov_w'], " mm", True),
    ("FOV Height", base_res['fov_h'], vals['fov_h'], " mm", True),
    ("Resolution", base_res['res'], vals['res'], " px/mm", True),
    ("Brightness", 100.0, vals['bright'], "%", True),
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

# --- PLOTS ---
sch_c1, sch_c2 = st.columns(2)
x_max = max(BASE_PARAMS["distance"], st.session_state.distance) + 250
balls_max_y = first_pos + (num_pos * spacing) + 100
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
global_x_max = max(BASE_PARAMS["distance"], st.session_state.distance) + 250

with sch_c1:
    st.pyplot(plot_schematic("Baseline", BASE_PARAMS["distance"], base_res, num_pos, baseline_first_pos, spacing, (-200, global_x_max), (global_y_min, global_y_max), False))
with sch_c2:
    st.pyplot(plot_schematic("Your Setup", st.session_state.distance, vals, num_pos, first_pos, spacing, (-200, global_x_max), (global_y_min, global_y_max), include_club))

lm_c1, lm_c2 = st.columns(2)
# Ensure LM view is wide enough for club data (-101.6mm)
base_min_x = min(base_res["fov_center"] - base_res["fov_w"]/2, vals["fov_center"] - vals["fov_w"]/2, -50) - 20
if include_club:
    base_min_x = min(base_min_x, -150)

all_min_x = base_min_x
all_max_x = max(base_res["fov_center"] + base_res["fov_w"]/2, vals["fov_center"] + vals["fov_w"]/2) + 50
all_max_y = max(base_res["fov_top_z_far"], vals["fov_top_z_far"]) + 50

with lm_c1:
    st.pyplot(plot_sensor_view_final("Baseline", base_res, num_pos, baseline_first_pos, spacing, 1, (all_min_x, all_max_x), (-50, all_max_y)))
with lm_c2:
    start_n = 3 if include_club else 1
    st.pyplot(plot_sensor_view_final("Your Setup", vals, num_pos, first_pos, spacing, start_n, (all_min_x, all_max_x), (-50, all_max_y), include_club=include_club))