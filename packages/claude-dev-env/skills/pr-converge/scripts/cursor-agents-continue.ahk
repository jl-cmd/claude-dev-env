; cursor-agents-continue.ahk
; Sends "continue" + Enter to a Cursor Agents window every 5 minutes when enabled.
; Toggle with Ctrl+Alt+A. Optional first CLI arg overrides the target window title substring.
; A small colored pill on the upper-right corner of the rightmost monitor shows ON/OFF state.

#Requires AutoHotkey v2.0
#SingleInstance Force

SetTitleMatchMode 2

DEFAULT_TARGET_WINDOW_TITLE := "Cursor Agents"
SEND_INTERVAL_MILLISECONDS  := 300000
ACTIVATION_TIMEOUT_SECONDS  := 2
FOCUS_SETTLE_SLEEP_MS       := 150
POST_TEXT_SLEEP_MS          := 50
CONTINUE_PHRASE             := "continue"

INDICATOR_DESIGN_WIDTH_PX        := 230
INDICATOR_DESIGN_HEIGHT_PX       := 28
INDICATOR_DESIGN_RIGHT_OFFSET_PX := 16
INDICATOR_DESIGN_TOP_OFFSET_PX   := 8
INDICATOR_TEXT_DESIGN_PADDING_PX := 4
INDICATOR_TEXT_DESIGN_HEIGHT_PX  := 20

INDICATOR_FONT_NAME       := "Segoe UI"
INDICATOR_FONT_POINT_SIZE := 9
INDICATOR_FONT_OPTIONS    := "s" INDICATOR_FONT_POINT_SIZE " cWhite Bold"

COLOR_OFF_BACKGROUND := "800000"
COLOR_ON_BACKGROUND  := "006400"
LABEL_OFF            := "AGENTS: OFF  (Ctrl+Alt+A)"
LABEL_ON             := "AGENTS: ON  (Ctrl+Alt+A)"

DPI_REFERENCE := 96

AUTO_START_FLAG := "--start-on"

INT32_MINIMUM_VALUE := -2147483648

terminate_other_script_instances() {
    stop_script := A_ScriptDir "\cursor-agents-continue-stop-others.ps1"
    if !FileExist(stop_script)
        return
    RunWait('pwsh -NoProfile -NoLogo -ExecutionPolicy Bypass -File "' stop_script '" -KeepProcessId ' ProcessExist(), , "Hide")
}

terminate_other_script_instances()

target_window_title := resolve_target_window_title_from_arguments()
should_auto_start := has_auto_start_flag()
is_enabled := false

indicator := unset
indicator_label := unset
build_indicator()
render_indicator(false)
if (should_auto_start)
    apply_enabled_state(true)

^!a:: {
    global is_enabled
    apply_enabled_state(!is_enabled)
}

apply_enabled_state(next_enabled) {
    global is_enabled
    is_enabled := next_enabled
    render_indicator(is_enabled)
    if (is_enabled) {
        send_continue_to_target()
        SetTimer(send_continue_to_target, SEND_INTERVAL_MILLISECONDS)
        return
    }
    SetTimer(send_continue_to_target, 0)
}

has_auto_start_flag() {
    each_arg_index := 1
    while (each_arg_index <= A_Args.Length) {
        if (A_Args[each_arg_index] = AUTO_START_FLAG)
            return true
        each_arg_index++
    }
    return false
}

resolve_target_window_title_from_arguments() {
    candidate := ""
    each_arg_index := 1
    while (each_arg_index <= A_Args.Length) {
        arg_value := A_Args[each_arg_index]
        if (arg_value = AUTO_START_FLAG) {
            each_arg_index++
            continue
        }
        if (candidate = "") {
            candidate := arg_value
        }
        each_arg_index++
    }
    if (candidate = "")
        return DEFAULT_TARGET_WINDOW_TITLE
    return IsInteger(candidate) ? "ahk_pid " candidate : candidate
}


build_indicator() {
    global indicator, indicator_label
    dpi_scale_factor := A_ScreenDPI / DPI_REFERENCE
    scaled_width        := Round(INDICATOR_DESIGN_WIDTH_PX        * dpi_scale_factor)
    scaled_height       := Round(INDICATOR_DESIGN_HEIGHT_PX       * dpi_scale_factor)
    scaled_right_offset := Round(INDICATOR_DESIGN_RIGHT_OFFSET_PX * dpi_scale_factor)
    scaled_top_offset   := Round(INDICATOR_DESIGN_TOP_OFFSET_PX   * dpi_scale_factor)
    scaled_text_padding := Round(INDICATOR_TEXT_DESIGN_PADDING_PX * dpi_scale_factor)
    scaled_text_height  := Round(INDICATOR_TEXT_DESIGN_HEIGHT_PX  * dpi_scale_factor)
    scaled_text_width   := scaled_width - (scaled_text_padding * 2)

    rightmost_monitor_bounds := find_rightmost_monitor_bounds()

    indicator := Gui("-Caption +AlwaysOnTop +ToolWindow -DPIScale")
    indicator.BackColor := COLOR_OFF_BACKGROUND
    indicator.SetFont(INDICATOR_FONT_OPTIONS, INDICATOR_FONT_NAME)
    indicator_label := indicator.Add(
        "Text",
        "x" scaled_text_padding " y" scaled_text_padding
        . " w" scaled_text_width " h" scaled_text_height
        . " Center BackgroundTrans",
        LABEL_OFF
    )

    indicator_x := rightmost_monitor_bounds.right_edge - scaled_width - scaled_right_offset
    indicator_y := rightmost_monitor_bounds.top_edge + scaled_top_offset
    indicator.Show("x" indicator_x " y" indicator_y " w" scaled_width " h" scaled_height " NoActivate")
}

render_indicator(is_currently_enabled) {
    global indicator, indicator_label
    indicator.BackColor := is_currently_enabled ? COLOR_ON_BACKGROUND : COLOR_OFF_BACKGROUND
    indicator_label.Text := is_currently_enabled ? LABEL_ON : LABEL_OFF
    WinRedraw("ahk_id " indicator.Hwnd)
}

send_continue_to_target() {
    global target_window_title
    if (!WinExist(target_window_title))
        return
    try {
        WinActivate(target_window_title)
        if (!WinWaitActive(target_window_title, , ACTIVATION_TIMEOUT_SECONDS))
            return
    } catch TargetError {
        return
    }
    Sleep FOCUS_SETTLE_SLEEP_MS
    SendText CONTINUE_PHRASE
    Sleep POST_TEXT_SLEEP_MS
    Send "{Enter}"
}

find_rightmost_monitor_bounds() {
    monitor_count := MonitorGetCount()
    rightmost_edge_px := INT32_MINIMUM_VALUE
    rightmost_monitor_top_px := 0
    loop monitor_count {
        MonitorGet(A_Index, &monitor_left, &monitor_top, &monitor_right, &monitor_bottom)
        if (monitor_right > rightmost_edge_px) {
            rightmost_edge_px := monitor_right
            rightmost_monitor_top_px := monitor_top
        }
    }
    return { right_edge: rightmost_edge_px, top_edge: rightmost_monitor_top_px }
}
