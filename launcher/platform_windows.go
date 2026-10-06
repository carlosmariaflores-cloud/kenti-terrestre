//go:build windows

package main

import (
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"
	"unsafe"
)

var (
	shell32  = syscall.NewLazyDLL("shell32.dll")
	ole32    = syscall.NewLazyDLL("ole32.dll")
	user32   = syscall.NewLazyDLL("user32.dll")
	pSHGetKF = shell32.NewProc("SHGetKnownFolderPath")
	pCoFree  = ole32.NewProc("CoTaskMemFree")
	pMsgBox  = user32.NewProc("MessageBoxW")
)

type guid struct {
	Data1 uint32
	Data2 uint16
	Data3 uint16
	Data4 [8]byte
}

// FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
var folderDocuments = guid{0xFDD39AD0, 0x238F, 0x46AF, [8]byte{0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7}}

// documentsDir devuelve la carpeta Documentos real (también si está en OneDrive).
func documentsDir() string {
	if pSHGetKF.Find() == nil {
		var p *uint16
		hr, _, _ := pSHGetKF.Call(uintptr(unsafe.Pointer(&folderDocuments)), 0, 0, uintptr(unsafe.Pointer(&p)))
		if hr == 0 && p != nil {
			defer pCoFree.Call(uintptr(unsafe.Pointer(p)))
			n := 0
			for *(*uint16)(unsafe.Pointer(uintptr(unsafe.Pointer(p)) + uintptr(n)*2)) != 0 {
				n++
			}
			s := syscall.UTF16ToString(unsafe.Slice(p, n))
			if s != "" {
				return s
			}
		}
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, "Documents")
}

func browsers() []string {
	var out []string
	add := func(env, rel string) {
		if base := os.Getenv(env); base != "" {
			out = append(out, filepath.Join(base, rel))
		}
	}
	add("ProgramFiles(x86)", `Microsoft\Edge\Application\msedge.exe`)
	add("ProgramFiles", `Microsoft\Edge\Application\msedge.exe`)
	add("LOCALAPPDATA", `Microsoft\Edge\Application\msedge.exe`)
	add("ProgramFiles", `Google\Chrome\Application\chrome.exe`)
	add("ProgramFiles(x86)", `Google\Chrome\Application\chrome.exe`)
	add("LOCALAPPDATA", `Google\Chrome\Application\chrome.exe`)
	return out
}

// openWindow abre la interfaz como ventana de aplicación. Devuelve un canal
// que se cierra cuando esa ventana termina, o nil si no se puede seguir.
func openWindow(url string) <-chan struct{} {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	profile := filepath.Join(base, folderName, "ventana")
	for _, b := range browsers() {
		if _, err := os.Stat(b); err != nil {
			continue
		}
		cmd := exec.Command(b,
			"--app="+url,
			"--user-data-dir="+profile,
			"--no-first-run",
			"--no-default-browser-check",
			"--disable-sync",
			"--window-size=1366,900",
		)
		if err := cmd.Start(); err != nil {
			log.Println("no se pudo abrir", b, err)
			continue
		}
		log.Println("ventana abierta con", b)
		done := make(chan struct{})
		go func() { cmd.Wait(); close(done) }()
		select {
		case <-done:
			// Se entregó a un proceso ya abierto: seguimos por señales de la página.
			return nil
		case <-time.After(5 * time.Second):
			return done
		}
	}
	log.Println("sin Edge ni Chrome: se usa el navegador predeterminado")
	c := exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	c.Start()
	return nil
}

func openFolder(dir string) {
	exec.Command("explorer", dir).Start()
}

// openFile abre un archivo con el programa que Windows tenga asociado (Excel).
func openFile(path string) {
	c := exec.Command("rundll32", "url.dll,FileProtocolHandler", path)
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	c.Start()
}

func fatal(msg string) {
	log.Println("ERROR:", msg)
	t, _ := syscall.UTF16PtrFromString(msg)
	c, _ := syscall.UTF16PtrFromString(appName)
	pMsgBox.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), 0x10)
	os.Exit(1)
}
