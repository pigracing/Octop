//go:build !production || darwin

package main

// Development builds look for Octop-<plat>.zip, Octop-portable-<plat>-*.zip or
// <display-name>-portable-<plat>-*.zip beside the executable. macOS production
// copies the zip into Resources as Octop-<plat>.zip.
var embeddedPortable []byte
