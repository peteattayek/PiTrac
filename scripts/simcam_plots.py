import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as mlines
import math
from simcam_data import BALL_RADIUS_MM, BALL_DIAMETER_MM

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

    lm_rect = patches.Rectangle((-150, fov_center_y - 75), 150, 150, 
                               linewidth=1, edgecolor='black', facecolor='#222222', alpha=0.9, zorder=20)
    ax.add_patch(lm_rect)
    ax.text(-75, fov_center_y, "LM", ha='center', va='center', color='white', fontweight='bold', zorder=21)

    for cx, cy in cam_centers:
        raw_top = cy + (raw_w / 2)
        raw_bot = cy - (raw_w / 2)
        if is_stereo:
            ax.plot([0, dist_mm], [cy, raw_top], color='gray', linestyle=':', alpha=0.3, zorder=1)
            ax.plot([0, dist_mm], [cy, raw_bot], color='gray', linestyle=':', alpha=0.3, zorder=1)
        else:
            ax.plot([0, dist_mm], [cy, raw_top], color='skyblue', linestyle='--', alpha=0.3, zorder=1)
            ax.plot([0, dist_mm], [cy, raw_bot], color='skyblue', linestyle='--', alpha=0.3, zorder=1)

    fov_top = fov_center_y + (fov_w_mm / 2)
    fov_bottom = fov_center_y - (fov_w_mm / 2)
    label_fov = 'Overlap FOV' if is_stereo else 'FOV'
    ax.fill([0, dist_mm, dist_mm], [fov_center_y, fov_top, fov_bottom], alpha=0.2, color='blue', label=label_fov, zorder=2)
    
    dof_near = vals["near_limit"]
    dof_far = vals["far_limit"]
    plot_far = min(dof_far, dist_mm + 500)
    dof_rect = patches.Rectangle((dof_near, fov_bottom), plot_far - dof_near, fov_w_mm, 
                                 linewidth=1, edgecolor='green', facecolor='green', alpha=0.15, zorder=3, label="Focus Zone")
    ax.add_patch(dof_rect)
    
    ax.axvline(dist_mm, color='red', linestyle=':', alpha=0.5, zorder=4)
    ax.plot(dist_mm, 0, 'kx', markersize=8, markeredgewidth=2, zorder=5)
    ax.text(dist_mm, -20, "Tee", ha='center', va='top', fontweight='bold', zorder=20)
    
    lbl_off = 35 
    
    if include_club:
        club_y_min = -101.6 
        club_y_max = 25.4   
        cx_min = dof_near
        cx_max = min(dof_far, x_limits[1] + 100)
        ax.plot([cx_min, cx_max], [club_y_min, club_y_min], color='red', linestyle=':', linewidth=1.5, zorder=4)
        ax.text(dist_mm + lbl_off, club_y_min, "1", color='blue', fontweight='bold', va='center', zorder=20)
        ax.plot([cx_min, cx_max], [club_y_max, club_y_max], color='red', linestyle=':', linewidth=1.5, zorder=4)
        ax.text(dist_mm + lbl_off, club_y_max, "2", color='blue', fontweight='bold', va='center', zorder=20)
    
    safe_near_dev = vals["safe_near_dev"]
    safe_far_dev = vals["safe_far_dev"]
    flight_dist = vals["flight_dist"]
    
    real_ball_handle = mlines.Line2D([], [], color='red', marker='o', linestyle='None', markersize=8, label='Straight Shot')
    ghost_ball_handle = mlines.Line2D([], [], color='red', marker='o', linestyle='None', 
                                      markersize=8, markerfacecolor='none', markeredgewidth=1.5, label='Min/Max HLA')
    
    for i in range(num_pos):
        y = first_pos + (i * spacing)
        ax.add_patch(patches.Circle((dist_mm, y), BALL_RADIUS_MM, facecolor='red', edgecolor='black', linewidth=0.5, zorder=10))
        
        if flight_dist > 0: scale = y / flight_dist
        else: scale = 0
        
        near_offset = safe_near_dev * scale
        far_offset = safe_far_dev * scale
        
        ax.add_patch(patches.Circle((dist_mm - near_offset, y), BALL_RADIUS_MM, linestyle='-', linewidth=1.5, edgecolor='red', facecolor='none', zorder=11))
        
        label_x = dist_mm + 40
        if safe_far_dev < 9000:
            ax.add_patch(patches.Circle((dist_mm + far_offset, y), BALL_RADIUS_MM, linestyle='-', linewidth=1.5, edgecolor='red', facecolor='none', zorder=11))
            label_x = dist_mm + far_offset + 30
            
    arrow_x = x_limits[1] - 50
    ax.arrow(arrow_x, 0, 0, 200, head_width=20, head_length=40, fc='k', ec='k', zorder=5)
    ax.text(arrow_x + 30, 100, "Swing Direction", rotation=90, va='center', zorder=5)

    ax.set_title(title + " (Top View)")
    ax.set_xlabel("Distance Perpendicular (mm)")
    ax.set_ylabel("Distance Parallel (mm)")
    ax.set_xlim(x_limits)
    ax.set_ylim(y_limits)
    ax.invert_xaxis()
    ax.set_aspect('equal', adjustable='box') 
    ax.grid(True, linestyle=':', alpha=0.6)
    
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
    
    is_stereo = vals["stereo_base"] > 0
    label_fov = 'Overlap FOV' if is_stereo else 'FOV'
    
    if include_club:
        club_x_1 = -101.6
        club_x_2 = 25.4
        ax.vlines(club_x_1, eff_bottom, eff_bottom + eff_height, colors='red', linestyles=':', linewidth=1.5, zorder=5)
        ax.text(club_x_1, eff_bottom + eff_height + 10, "1", color='blue', fontweight='bold', ha='center', fontsize=10)
        ax.vlines(club_x_2, eff_bottom, eff_bottom + eff_height, colors='red', linestyles=':', linewidth=1.5, zorder=5)
        ax.text(club_x_2, eff_bottom + eff_height + 10, "2", color='blue', fontweight='bold', ha='center', fontsize=10)

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

    rect = patches.Rectangle((rect_left, eff_bottom), eff_width, eff_height,
                             linewidth=2, edgecolor='blue', facecolor='skyblue', alpha=0.1, label=label_fov)
    ax.add_patch(rect)
    
    ax.plot(0, 0, 'kx', markersize=12, markeredgewidth=2)
    ax.text(0, -15, "Tee", ha='center', va='top', fontsize=8)
    ax.axhline(0, color='gray', linestyle='-', alpha=0.5)
    
    min_rad = vals["min_v_rad"]
    max_rad = vals["max_v_rad"]
    
    for i in range(num_pos):
        h_pos = first_pos + (i * spacing)
        h_max = BALL_RADIUS_MM + (h_pos * math.tan(max_rad))
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
    
    vla_handle = mlines.Line2D([], [], color='orange', marker='o', linestyle='None', markeredgecolor='black', markersize=8, alpha=0.8, label='Min/Max VLA')
    handles, labels = ax.get_legend_handles_labels()
    final_handles = []
    final_labels = []
    for h, l in zip(handles, labels):
        final_handles.append(h)
        final_labels.append(l)
    final_handles.append(vla_handle)
    final_labels.append("Min/Max VLA")
    ax.legend(final_handles, final_labels, loc='best', fontsize='small', framealpha=0.9)
    return fig
