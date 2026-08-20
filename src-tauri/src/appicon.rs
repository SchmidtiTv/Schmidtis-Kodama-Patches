// App-icon personalization (Stufe 1 + 3).
//
// Stufe 1 (all platforms): change the *running* app's icon — the taskbar/window icon on
// Windows and the menu-bar tray icon — via Tauri's own Image API. This is what the user
// sees while the app is open. The static pinned-shortcut / .exe icon is NOT touched.
//
// Stufe 3 (macOS only): additionally set the Dock icon (NSApplication, live). We intentionally
// leave the .app bundle icon alone so macOS can render the bundled layered icon in Finder, the
// Dock, and Cmd–Tab. Cocoa calls must run on the main thread.

use tauri::Manager;

#[cfg(target_os = "macos")]
fn macos_custom_app_icons_enabled() -> bool {
    matches!(option_env!("KODAMA_APP_ICON_STYLE"), Some("classic"))
}

#[tauri::command]
pub fn app_icon_customization_available() -> bool {
    #[cfg(target_os = "macos")]
    return macos_custom_app_icons_enabled();

    #[cfg(not(target_os = "macos"))]
    true
}

#[tauri::command]
pub fn set_app_icon(app: tauri::AppHandle, file: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    if !macos_custom_app_icons_enabled() {
        return Err("App icon customization is unavailable in adaptive icon builds.".into());
    }

    // Guard against path traversal: only a bare file name is allowed.
    if file.contains('/') || file.contains('\\') || file.contains("..") {
        return Err("invalid icon name".into());
    }

    let res_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
    let icon_path = res_dir.join("App-Icons").join(&file);
    if !icon_path.exists() {
        return Err(format!("icon not found: {}", icon_path.display()));
    }

    // Stufe 1: window + tray icon (cross-platform, via the image-png feature).
    let image = tauri::image::Image::from_path(&icon_path).map_err(|e| e.to_string())?;
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.set_icon(image.clone());
    }
    if let Some(tray) = app.try_state::<crate::AppTray>() {
        let _ = tray.0.set_icon(Some(image.clone()));
    }

    // Stufe 3: macOS Dock (live).
    #[cfg(target_os = "macos")]
    {
        let path_str = icon_path.to_string_lossy().to_string();
        let _ = app.run_on_main_thread(move || unsafe { set_macos_icon(&path_str) });
    }

    Ok(())
}

#[cfg(target_os = "macos")]
#[allow(unexpected_cfgs)]
pub unsafe fn clear_legacy_macos_bundle_icon() {
    use cocoa::base::{id, nil};
    use objc::{class, msg_send, sel, sel_impl};

    // Older versions wrote a custom `Icon\r` resource onto the app bundle. That
    // overrides the bundled Icon Composer asset, even after the app is updated.
    let workspace: id = msg_send![class!(NSWorkspace), sharedWorkspace];
    let bundle: id = msg_send![class!(NSBundle), mainBundle];
    let bundle_path: id = msg_send![bundle, bundlePath];
    let _: bool = msg_send![workspace, setIcon: nil forFile: bundle_path options: 0u64];
}

#[cfg(target_os = "macos")]
// `objc` 0.2's message macros still probe its historical `cargo-clippy` feature.
// Keep the compatibility warning contained to this legacy Cocoa interop.
#[allow(unexpected_cfgs)]
unsafe fn set_macos_icon(png_path: &str) {
    use cocoa::appkit::NSCompositingOperation;
    use cocoa::base::{id, nil};
    use cocoa::foundation::{NSPoint, NSRect, NSSize, NSString};
    use objc::{class, msg_send, sel, sel_impl};

    // macOS sizes app-switcher slots by image canvas, not the visible artwork. The
    // selectable PNGs are full-bleed, unlike most native macOS icons, so preserve
    // an optical safe area before giving the image to AppKit.
    const ICON_ARTWORK_SCALE: f64 = 0.84;

    let path: id = NSString::alloc(nil).init_str(png_path);
    let source_image: id = msg_send![class!(NSImage), alloc];
    let source_image: id = msg_send![source_image, initWithContentsOfFile: path];
    if source_image == nil {
        return;
    }

    let source_size: NSSize = msg_send![source_image, size];
    if source_size.width <= 0.0 || source_size.height <= 0.0 {
        return;
    }
    let inset_x = source_size.width * (1.0 - ICON_ARTWORK_SCALE) / 2.0;
    let inset_y = source_size.height * (1.0 - ICON_ARTWORK_SCALE) / 2.0;
    let destination_rect = NSRect::new(
        NSPoint::new(inset_x, inset_y),
        NSSize::new(
            source_size.width * ICON_ARTWORK_SCALE,
            source_size.height * ICON_ARTWORK_SCALE,
        ),
    );
    let source_rect = NSRect::new(NSPoint::new(0.0, 0.0), source_size);

    let image: id = msg_send![class!(NSImage), alloc];
    let image: id = msg_send![image, initWithSize: source_size];
    let _: () = msg_send![image, lockFocus];
    let _: () = msg_send![source_image,
        drawInRect: destination_rect
        fromRect: source_rect
        operation: NSCompositingOperation::NSCompositeSourceOver
        fraction: 1.0f64
    ];
    let _: () = msg_send![image, unlockFocus];

    // Dock icon of the running instance.
    let nsapp: id = msg_send![class!(NSApplication), sharedApplication];
    let _: () = msg_send![nsapp, setApplicationIconImage: image];
}
