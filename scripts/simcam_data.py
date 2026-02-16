# --- CONFIGURATION & CONSTANTS ---
BALL_DIAMETER_MM = 42.67
BALL_RADIUS_MM = BALL_DIAMETER_MM / 2

# BASELINE HARDWARE (DEFAULT REFERENCE)
DEFAULT_BASE_PARAMS = {
    "sensor": {
        "width_px": 1440, "height_px": 1080, "pixel_size": 3.45, 
        "format": "1/2.9", "qe": {730: 0.30, 780: 0.25, 810: 0.21, 850: 0.15, 940: 0.07}
    },
    "focal": 6.0,
    "aperture": 1.2,
    "distance": 430,      # Fixed X (Camera Dist)
    "height_target": 90,  # Fixed Z (Camera Height)
    "y_pos": 530,         # Fixed Y (Horizontal Center)
    "wavelength": 810,
    "binning": False,
    "focus_offset": 0,
    "include_club": False,
    "is_stereo": False,
    "stereo_base": 0,
    "stereo_align": "Horizontal"
}

# SENSOR DATABASE
SENSORS = {
    "IMX296 (1.6MP Global Shutter)": {
        "width_px": 1440, "height_px": 1080, "pixel_size": 3.45, "format": "1/2.9",
        "shutter": "Global", "nir_tech": None,
        "qe": {730: 0.30, 780: 0.25, 810: 0.21, 850: 0.15, 940: 0.07}
    },
    "OV9281 (1.0MP Global Shutter)": {
        "width_px": 1280, "height_px": 800, "pixel_size": 3.0, "format": "1/4",
        "shutter": "Global", "nir_tech": None,
        "qe": {730: 0.35, 780: 0.31, 810: 0.28, 850: 0.20, 940: 0.09}
    },
    "AR0234 (2.3MP Global Shutter)": {
        "width_px": 1920, "height_px": 1200, "pixel_size": 3.0, "format": "1/2.6",
        "shutter": "Global", "nir_tech": None,
        "qe": {730: 0.32, 780: 0.28, 810: 0.25, 850: 0.19, 940: 0.07}
    },
    "OS08A20 (8.3MP Rolling Shutter)": {
        "width_px": 3840, "height_px": 2160, "pixel_size": 2.0, "format": "1/1.8",
        "shutter": "Rolling", "nir_tech": "Nyxel™",
        "qe": {730: 0.75, 780: 0.72, 810: 0.70, 850: 0.60, 940: 0.40}
    },
    "OG05B1B (5.0MP Global Shutter)": {
        "width_px": 2592, "height_px": 1944, "pixel_size": 2.2, "format": "1/2.5",
        "shutter": "Global", "nir_tech": "Nyxel™",
        "qe": {730: 0.70, 780: 0.68, 810: 0.65, 850: 0.60, 940: 0.40}
    },
    "IMX678 (8.3MP Rolling Shutter)": {
        "width_px": 3840, "height_px": 2160, "pixel_size": 2.0, "format": "1/1.8",
        "shutter": "Rolling", "nir_tech": "Starvis 2",
        "qe": {730: 0.55, 780: 0.52, 810: 0.50, 850: 0.45, 940: 0.25}
    },
     "AR0822 (8.3MP Rolling Shutter)": {
        "width_px": 3840, "height_px": 2160, "pixel_size": 2.0, "format": "1/1.8",
        "shutter": "Rolling", "nir_tech": "NIR+",
        "qe": {730: 0.62, 780: 0.60, 810: 0.58, 850: 0.49, 940: 0.29}
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

# --- LENS DATABASE ---
RAW_LENS_DATABASE = [
    ("Varifocal 2.8-12mm", (2.8, 12.0), (1.6, 16.0), 9.0),
    ("Arducam LN081", 4.5, 2.0, 9.0), ("Arducam LN079", 5.5, 2.8, 9.0),
    ("Arducam LN078", 8.5, 3.0, 9.0), ("Arducam LN077", 12.0, 2.8, 9.0),
    ("Arducam LN076", 16.0, 2.8, 9.0), ("Arducam LN075", 25.0, 2.8, 9.0),
    ("Arducam M25156H18", 1.56, 2.0, 7.7), ("Arducam M27210H08", 2.1, 2.0, 6.6),  
    ("Arducam M23272M14", 2.27, 2.5, 7.7), ("Arducam M27280M07S", 2.8, 2.8, 6.6), 
    ("Arducam M23356H09", 3.56, 2.5, 7.7), ("Arducam M25360H06S", 3.6, 3.0, 7.1), 
    ("Arducam M2306ZM13", 6.0, 2.0, 7.7), ("Arducam M2506ZH04", 6.0, 2.0, 7.1),  
    ("Arducam M2508ZH02", 8.0, 2.0, 7.1), ("Arducam M2512ZH03", 12.0, 2.0, 7.1), 
    ("Arducam M2516ZH01", 16.0, 2.0, 7.1), ("Arducam M2025ZM02", 25.0, 2.0, 7.7), 
    ("Arducam CS 6mm F1.2", 6.0, (1.2, 16.0), 8.0), ("Arducam CS 6mm", 6.0, 1.4, 7.7),
    ("Arducam CS 8mm", 8.0, 1.4, 7.7), ("Arducam CS 12mm", 12.0, 1.6, 7.7),
    ("Arducam CS 16mm", 16.0, 1.6, 7.7), ("Arducam CS 25mm", 25.0, 1.2, 7.7),
    ("Arducam C 16mm", 16.0, (1.6, 16.0), 11.0), ("Arducam C 25mm", 25.0, (1.4, 16.0), 16.0),
    ("Arducam C 35mm", 35.0, (1.6, 16.0), 11.0), ("Arducam C 50mm", 50.0, (1.8, 16.0), 11.0), 
    ("CIL207", 0.8, 1.9, 4.0), ("CIL208", 0.9, 2.2, 2.9), ("CIL212", 1.1, 2.2, 3.9),
    ("CIL273", 1.3, 2.0, 5.8), ("CIL293", 1.3, 2.2, 5.4), ("CIL914", 1.4, 2.3, 4.5),
    ("CIL215", 1.5, 2.0, 4.2), ("CIL216", 1.55, 2.2, 4.7), ("CIL217", 1.7, 2.7, 5.7),
    ("CIL237", 1.7, 2.2, 5.5), ("CIL018", 1.8, 2.8, 7.0), ("CIL019", 1.8, 1.6, 6.6),
    ("CIL239", 1.8, 2.0, 5.2), ("CIL818", 1.8, 2.0, 5.2), ("CIL220-F2.3", 1.83, 2.3, 6.8),
    ("CIL220-F2.8", 1.83, 2.8, 6.8), ("CIL219", 1.9, 2.5, 6.3), ("CIL290", 1.9, 2.2, 5.7),
    ("CIL819", 1.9, 2.0, 5.9), ("CIL281", 2.0, 1.8, 6.5), ("CIL821", 2.1, 2.4, 6.8),
    ("CIL023", 2.2, 2.2, 7.8), ("CIL222", 2.2, 2.0, 6.6), ("CIL282", 2.2, 1.8, 6.8),
    ("CIL292", 2.3, 2.1, 7.2), ("CIL324", 2.4, 1.9, 7.0), ("CIL825", 2.5, 2.0, 6.8),
    ("CIL926", 2.5, 2.5, 7.4), ("CIL028-F2.3", 2.6, 2.3, 8.0), ("CIL028-F2.6", 2.6, 2.6, 8.0),
    ("CIL027", 2.7, 2.8, 8.2), ("CIL227", 2.7, 2.5, 8.2), ("CIL327-F1.5", 2.7, 1.5, 7.1),
    ("CIL327-F1.8", 2.7, 1.8, 7.1), ("CIL093", 2.8, 2.4, 7.8), ("CIL329", 2.8, 2.0, 7.2),
    ("CIL326", 2.9, 1.4, 6.8), ("CIL829", 2.9, 2.5, 6.8), ("CIL330", 2.94, 2.6, 8.0),
    ("CIL391", 2.94, 2.6, 8.0), ("CIL030", 3.0, 2.1, 9.4), ("CIL232", 3.1, 1.9, 9.1),
    ("CIL332", 3.2, 1.8, 7.2), ("CIL034-F2.3", 3.24, 2.3, 8.2), ("CIL034-F2.7", 3.24, 2.7, 8.2),
    ("CIL034-F4.2", 3.24, 4.2, 8.2), ("CIL036", 3.3, 2.2, 7.2), ("CIL394", 3.45, 2.1, 7.6),
    ("CIL333", 3.5, 2.4, 8.8), ("CIL334", 3.5, 2.2, 9.4), ("CIL335", 3.5, 1.8, 7.8),
    ("CIL336", 3.6, 1.9, 7.4), ("CIL337", 3.6, 1.6, 7.5), ("CIL038", 3.8, 3.0, 7.8),
    ("CIL039", 3.9, 2.8, 8.0), ("CIL339", 3.9, 1.6, 9.3), ("CIL340", 4.0, 2.0, 9.0),
    ("CIL341", 4.0, 2.0, 9.4), ("CIL042", 4.2, 1.9, 9.4), ("CIL043", 4.3, 3.2, 8.1),
    ("CIL046", 4.4, 2.0, 9.1), ("CIL343", 4.4, 2.3, 8.8), ("CIL045", 4.5, 3.5, 7.2),
    ("CIL344-F1.9", 4.5, 1.9, 11.0), ("CIL344-F2.7", 4.5, 2.7, 11.0), ("CIL948", 4.8, 2.0, 7.6),
    ("CIL052", 5.2, 3.4, 9.3), ("CIL355", 5.5, 1.8, 7.0), ("CIL056", 5.5, 2.4, 8.0),
    ("CIL857", 5.7, 3.0, 7.0), ("CIL359", 5.78, 1.6, 7.5), ("CIL358", 5.8, 1.9, 9.3),
    ("CIL059-F1.7", 5.9, 1.7, 9.3), ("CIL059-F4.0", 5.9, 4.0, 9.3), ("CIL059-F5.6", 5.9, 5.6, 9.3),
    ("CIL061", 6.0, 1.9, 7.4), ("CIL361", 6.1, 1.8, 7.4), ("CIL062-F2.8", 6.2, 2.8, 9.0),
    ("CIL062-F4.0", 6.2, 4.0, 9.0), ("CIL068", 6.8, 2.5, 8.8), ("CIL368", 6.8, 1.8, 9.4),
    ("CIL872", 7.2, 2.5, 8.5), ("CIL078", 7.8, 2.0, 9.3), ("CIL382-F2.0", 7.8, 2.0, 7.4),
    ("CIL382-F5.6", 7.8, 5.6, 7.4), ("CIL079", 7.9, 2.0, 7.6), ("CIL083", 8.0, 2.8, 9.0),
    ("CIL085-F3.0", 8.2, 3.0, 8.8), ("CIL085-F4.4", 8.2, 4.4, 8.8), ("CIL092", 9.2, 2.6, 9.3),
    ("CIL104", 10.4, 3.8, 7.2), ("CIL122", 12.0, 2.0, 9.3), ("CIL120", 12.2, 2.4, 8.0),
    ("CIL123", 12.5, 2.3, 8.0), ("CIL125-F2.4", 12.5, 2.4, 8.2), ("CIL125-F3.6", 12.5, 3.6, 8.2),
    ("CIL125-F8.0", 12.5, 8.0, 8.2), ("CIL142-F2.6", 14.4, 2.6, 9.3), ("CIL142-F4.1", 14.4, 4.1, 9.3),
    ("CIL142-F5.2", 14.4, 5.2, 9.3), ("CIL160-F1.9", 16.0, 1.9, 8.4), ("CIL160-F2.8", 16.0, 2.8, 8.4),
    ("CIL160-F4.0", 16.0, 4.0, 8.4), ("CIL160-F5.6", 16.0, 5.6, 8.4), ("CIL161", 16.0, 2.0, 8.0),
    ("CIL178", 17.8, 2.0, 7.2), ("CIL190", 19.0, 1.6, 7.2), ("CIL121-F2.8", 21.8, 2.8, 9.3),
    ("CIL121-F5.9", 21.8, 5.9, 9.3), ("CIL250", 25.0, 2.4, 9.4), ("CIL350", 35.0, 2.4, 11.0),
    ("CIL051", 50.0, 2.8, 9.4), ("CIL075", 75.0, 3.5, 9.4),
    ("CIL570 (C-Mt)", 4.0, (2.0, 16.0), 9.3), ("CIL571 (C-Mt)", 6.0, (2.1, 16.0), 9.3),
    ("CIL508 (C-Mt)", 8.5, (2.4, 16.0), 17.6), ("CIL521 (C-Mt)", 8.0, (1.5, 16.0), 11.0),
    ("CIL531 (C-Mt)", 8.0, (2.8, 16.0), 11.0), ("CIL512 (C-Mt)", 12.0, (2.8, 16.0), 17.6),
    ("CIL522 (C-Mt)", 12.0, (1.4, 16.0), 11.0), ("CIL532 (C-Mt)", 12.0, (2.0, 16.0), 11.0),
    ("CIL542 (C-Mt)", 12.0, (2.8, 16.0), 17.6), ("CIL552 (C-Mt)", 12.0, (2.8, 16.0), 19.3),
    ("CIL513 (C-Mt)", 16.0, (2.8, 16.0), 17.6), ("CIL523 (C-Mt)", 16.0, (1.4, 16.0), 11.0),
    ("CIL533 (C-Mt)", 16.0, (2.0, 16.0), 11.0), ("CIL553 (C-Mt)", 16.0, (2.8, 16.0), 19.3),
    ("CIL514 (C-Mt)", 25.0, (2.8, 16.0), 17.6), ("CIL525 (C-Mt)", 25.0, (1.4, 16.0), 11.0),
    ("CIL534 (C-Mt)", 25.0, (2.0, 16.0), 11.0), ("CIL544 (C-Mt)", 25.0, (1.8, 16.0), 17.6),
    ("CIL554 (C-Mt)", 25.0, (2.6, 16.0), 19.3), ("CIL515 (C-Mt)", 35.0, (2.8, 16.0), 17.6),
    ("CIL526 (C-Mt)", 35.0, (1.5, 16.0), 11.0), ("CIL535 (C-Mt)", 35.0, (2.0, 16.0), 11.0),
    ("CIL545 (C-Mt)", 35.0, (2.8, 16.0), 17.6), ("CIL555 (C-Mt)", 35.0, (2.6, 16.0), 19.3),
    ("CIL536 (C-Mt)", 50.0, (2.8, 16.0), 11.0), ("CIL546 (C-Mt)", 50.0, (2.8, 16.0), 17.6),
    ("CIL556 (C-Mt)", 50.0, (2.8, 16.0), 19.3), ("CIL557 (C-Mt)", 75.0, (3.0, 16.0), 19.3),
    ("CIL579 (C-Mt)", 75.0, (3.0, 16.0), 9.0), ("CIL505 (C-Mt)", 2.2, (2.2, 16.0), 14.2)
]

# --- EXPANDED LENS DATABASE ---
LENS_DATABASE = []
for model, focal_data, aper_data, img_circle in RAW_LENS_DATABASE:
    # 1. Expand Focal Lengths
    if isinstance(focal_data, tuple):
        min_f, max_f = focal_data
        focals = []
        curr_f = min_f
        while curr_f <= max_f + 0.001:
            focals.append(round(curr_f, 1))
            curr_f += 0.1
    else:
        focals = [focal_data]

    # 2. Expand Apertures
    if isinstance(aper_data, tuple):
        min_a, max_a = aper_data
        apers = []
        curr_a = min_a
        while curr_a <= max_a + 0.001:
            apers.append(round(curr_a, 1))
            curr_a += 0.1
    else:
        apers = [aper_data]
    
    is_varifocal_lens = isinstance(focal_data, tuple)

    # 3. Create Combinations
    for f in focals:
        for a in apers:
            LENS_DATABASE.append((model, f, a, img_circle, is_varifocal_lens))