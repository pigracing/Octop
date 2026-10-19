//go:build !darwin

package main

import (
	"github.com/wailsapp/wails/v3/pkg/application"
)

func applyTrayIcon(tray *application.SystemTray) {
	tray.SetIcon(trayIconPNG)
}

func applyAppIcon(app *application.App) {
	app.SetIcon(trayIconPNG)
}
