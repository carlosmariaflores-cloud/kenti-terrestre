//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

func documentsDir() string {
	if d := os.Getenv("KENTI_DOCS"); d != "" {
		return d
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, "Documents")
}

func openWindow(url string) <-chan struct{} {
	fmt.Println(appName, "en", url)
	if os.Getenv("KENTI_NO_BROWSER") != "" {
		return nil
	}
	if runtime.GOOS == "darwin" {
		exec.Command("open", url).Start()
	} else {
		exec.Command("xdg-open", url).Start()
	}
	return nil
}

func openFolder(dir string) { openFile(dir) }

func openFile(path string) {
	if runtime.GOOS == "darwin" {
		exec.Command("open", path).Start()
	} else {
		exec.Command("xdg-open", path).Start()
	}
}

func fatal(msg string) {
	fmt.Fprintln(os.Stderr, "ERROR:", msg)
	os.Exit(1)
}
