package main

import _ "embed"

// Defaults compiled into the shell. desktop/src/build/apply_branding.py writes
// branding_generated.go, whose init() overrides these values from
// desktop/branding.json; without that file the defaults keep the upstream brand.
//
//go:embed assets/tray-icon.png
var defaultTrayIconPNG []byte

//go:embed assets/tray-icon-template.png
var defaultTrayTemplatePNG []byte

var (
	productDisplayName  = "Octop"
	trayIconPNG         = defaultTrayIconPNG
	trayIconTemplatePNG = defaultTrayTemplatePNG
)
