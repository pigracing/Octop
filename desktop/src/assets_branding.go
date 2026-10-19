package main

import (
	"bytes"
	"html"
	"io/fs"
	"net/http"

	"github.com/wailsapp/wails/v3/pkg/application"
)

const appNamePlaceholder = "{{APP_NAME}}"

// brandedAssets serves the embedded shell assets and substitutes the product
// name in index.html. The shell page is embedded as static HTML, so the
// display name is injected at request time instead of rewriting tracked files.
func brandedAssets(assets fs.FS) http.Handler {
	base := application.BundledAssetFileServer(assets)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" || r.URL.Path == "/index.html" {
			data, err := fs.ReadFile(assets, "assets/index.html")
			if err == nil {
				data = bytes.ReplaceAll(
					data,
					[]byte(appNamePlaceholder),
					[]byte(html.EscapeString(productDisplayName)),
				)
				w.Header().Set("Content-Type", "text/html; charset=utf-8")
				_, _ = w.Write(data)
				return
			}
		}
		base.ServeHTTP(w, r)
	})
}
