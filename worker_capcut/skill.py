"""
CapCut Skill Knowledge base and validation logic.
"""

# Valid Transition names in CapCut (case-sensitive)
VALID_TRANSITIONS = {
    "Mix", "Black_Fade", "White_Flash", "Dissolve", "Slide", "Glitch",
    "Inhale", "Pull_in", "Pull_Out", "Flame", "Rainbow_Warp", "RGB_Glitch",
    "Cartoon_Swirl", "Cube", "Shutter", "Whirlpool", "Distortion",
    "Axis_Rotation", "Stretch_Right", "Stretch_Left", "Squeeze",
    "Montage_Snippets", "Then_and_Now", "Gradient_Wipe", "Black_smoke",
    "White_smoke", "BW_Flash", "Rainbow_Filter", "Urban_Glitch",
    "Camera_Glow", "Light_Sweep_II", "Flash", "Light_Beam", "Burn",
    "Blanch", "Fold_Over", "Bottom_Left_II", "Vertical_Blur_II", "Shake_3",
    "Rotate_CW_II", "Rotate_CCW_II", "CW_Swirl", "Right", "AntiCW_Swirl",
    "Transform_Shimmer", "Twinkle_Zoom", "Horizontal_Blur", "Radial_Blur",
    "Blurred_Highlight", "Vertical_Blur", "Blur", "Woosh", "Particles",
    "Mosaic", "Blink", "Flip_II", "Flip", "Left", "Up", "Wipe_Right",
    "Open_Horizontally", "Wipe_Up", "Wipe_Left", "Open_Vertically",
    "Curling_Wave", "Blue_Lines", "Recorder", "Like", "Little_Devil",
    "Super_Like", "Lightning", "Snow", "White_Ink", "Cloud", "Wave_Right",
    "Wave_Left", "Dots_Right", "Circular_Slices_II", "Split_III",
    "Horizontal_Slice", "Diagonal_Slices", "Split", "Vertical_Slices",
    "Split_IV", "Vintage_Screening", "Switch", "Open", "Page_Turning",
    "Clock_wipe", "Windmill", "Color_Glitch", "Strobe", "Blocks",
    "Horizontal_Lines", "Cutout_Flip", "Color_Swirl", "Shutter_II",
    "Stretch_ll", "Stretch", "Whirlpool", "Distortion", "Squeeze"
}

# Valid Intro Animations in CapCut (case-sensitive)
VALID_INTRO_ANIMS = {
    "Fade_In", "Zoom_1", "Slide_Down", "Slide_Up", "Slide_Right", "Slide_Left",
    "Rotate", "Zoom_Out", "Zoom_In", "Shake_3", "Shake_1", "Shake_2", "Flip",
    "Mini_Zoom", "Flame_Risen", "Rotation_Opening", "Retro_Fadein",
    "Retro_Fadein_2", "Screen_Wipe", "RGB_Scanlines", "CRT_Bands",
    "Vibrating_Panels", "Swing_Top_Right", "Anime_Frame", "Rock_Horizontally",
    "Gray_Mask", "Spin_Up_2", "Whirl", "Spin_Up_1", "Swing_Bottom",
    "Swing_Right", "Swing_Bottom_Left", "Blinds", "Swing_Bottom_Right",
    "Puzzle", "Swing_Top_Left", "Shake_Down", "Swing", "Wiper",
    "Roll_Right", "Spin_Left"
}

# Valid Outro Animations in CapCut (case-sensitive)
VALID_OUTRO_ANIMS = {
    "Fade_Out", "Slide_Down", "Slide_Up", "Slide_Right", "Slide_Left",
    "Zoom_In", "Zoom_Out", "Rotate", "Flip", "Mini_Zoom", "RGB_Scanlines",
    "Blurred_Fadein", "Blurred_Fadein_1", "CRT_Bands", "Flame_Risen",
    "Screen_Wipe", "Rotation_Closing", "Anime_Frame", "Rotate_Out_1",
    "Gray_Mask", "Whirl", "Vibrating_Panels", "Rotate_Out_2"
}

def get_skill_markdown() -> str:
    """
    Returns a beautifully formatted markdown of CapCut skills
    to be injected into the AI Agent's system prompt context.
    """
    return f"""
# CAPCUT EDITING SKILLS & METADATA DOCUMENTATION

You must use these exact case-sensitive strings for transitions and animations. Any parameter not in these lists will fail the video rendering engine.

## 1. Supported Transitions (between video/image clips)
Choose from: {', '.join(sorted(list(VALID_TRANSITIONS)))}

*CRITICAL RULES FOR TRANSITIONS*:
- transitions can only be placed BETWEEN clips.
- 'fade_in' and 'fade_out' are NOT transitions. In CapCut, they are INTRO/OUTRO ANIMATIONS.
- If the abstract kịch bản requests a 'fade_in' transition, map it to 'Dissolve' (or 'Mix') as the transition, and set the segment's 'intro_animation' to 'Fade_In'.
- If the abstract kịch bản requests a 'fade_out' transition, map it to 'Dissolve' (or 'Mix') as the transition, and set the segment's 'outro_animation' to 'Fade_Out'.

## 2. Supported Intro Animations (entrance animations for a clip)
Choose from: {', '.join(sorted(list(VALID_INTRO_ANIMS)))}

## 3. Supported Outro Animations (exit animations for a clip)
Choose from: {', '.join(sorted(list(VALID_OUTRO_ANIMS)))}
"""

def sanitize_segment(seg: dict) -> dict:
    """
    Validates and sanitizes a segment's parameters against valid CapCut metadata.
    If a parameter is invalid, it strips it or maps it to None to prevent VectCutAPI errors.
    """
    sanitized = dict(seg)
    
    # 1. Sanitize Transition
    trans = sanitized.get("transition")
    if trans:
        # Check case-sensitive exact match
        if trans not in VALID_TRANSITIONS:
            # Check case-insensitive match
            matching = [t for t in VALID_TRANSITIONS if t.lower() == trans.lower()]
            if matching:
                sanitized["transition"] = matching[0]
            else:
                # Strip invalid transition to prevent crash
                sanitized.pop("transition", None)
                sanitized.pop("transition_duration", None)
                
    # 2. Sanitize Intro Animation
    intro = sanitized.get("intro_animation")
    if intro:
        if intro not in VALID_INTRO_ANIMS:
            matching = [i for i in VALID_INTRO_ANIMS if i.lower() == intro.lower()]
            if matching:
                sanitized["intro_animation"] = matching[0]
            else:
                sanitized.pop("intro_animation", None)
                sanitized.pop("intro_animation_duration", None)
                
    # 3. Sanitize Outro Animation
    outro = sanitized.get("outro_animation")
    if outro:
        if outro not in VALID_OUTRO_ANIMS:
            matching = [o for o in VALID_OUTRO_ANIMS if o.lower() == outro.lower()]
            if matching:
                sanitized["outro_animation"] = matching[0]
            else:
                sanitized.pop("outro_animation", None)
                sanitized.pop("outro_animation_duration", None)
                
    return sanitized
