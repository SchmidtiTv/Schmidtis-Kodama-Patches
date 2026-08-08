import os

application = defines["application"]
background = defines["background"]

format = "UDZO"
files = [application]
symlinks = {"Applications": "/Applications"}

icon_size = 128
window_rect = ((100, 100), (900, 520))
icon_locations = {
    os.path.basename(application): (250, 260),
    "Applications": (600, 260),
}
