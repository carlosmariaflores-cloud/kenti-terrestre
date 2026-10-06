// Kenti Terrestre — flora, aves, mamíferos, herpetofauna y entomología en un
// solo programa, con pantalla de inicio y análisis global.
//
// Sirve la interfaz (embebida) en 127.0.0.1 y la abre en una ventana propia de
// Edge o Chrome. Cada especialidad guarda sus datos en su propia subcarpeta de
// Documentos\Kenti Terrestre. Sin dependencias externas: sólo la biblioteca
// estándar de Go.
package main

import (
	"bytes"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

//go:embed web
var webFS embed.FS

const version = "0.1.1"

// Valores fijados al compilar (-ldflags -X main.appID=...).
var (
	appID      = "kenti-terrestre"
	appName    = "Kenti Terrestre"
	folderName = "Kenti Terrestre"
	portText   = "47850"
)

// Una especialidad: su interfaz es web/g/<id>.html, sus datos van en
// Documentos\Kenti Terrestre\<sub>\<dataName>.
type group struct {
	id, nombre, appID, sub, dataName, legacy string // legacy: carpeta del módulo suelto en Documentos

	mu       sync.Mutex
	backedUp bool
}

var groups = []*group{
	{id: "flora", nombre: "Flora", appID: "kenti-botanico", sub: "Flora", dataName: "datos-botanica.json", legacy: "Kenti Botanico"},
	{id: "aves", nombre: "Aves", appID: "kenti-ornitologico", sub: "Aves", dataName: "datos-ornitologia.json", legacy: "Kenti Ornitologico"},
	{id: "mamiferos", nombre: "Mamíferos", appID: "kenti-mastozoologico", sub: "Mamiferos", dataName: "datos-mastozoologia.json", legacy: "Kenti Mastozoologico"},
	{id: "herpetos", nombre: "Herpetofauna", appID: "kenti-herpetologico", sub: "Herpetofauna", dataName: "datos-herpetologia.json", legacy: "Kenti Herpetologico"},
	{id: "insectos", nombre: "Entomología", appID: "kenti-entomologico", sub: "Entomologia", dataName: "datos-entomologia.json", legacy: "Kenti Entomologico"},
	{id: "global", nombre: "Análisis global", appID: "kenti-master-terrestre", sub: "Analisis global", dataName: "datos-analisis-global.json"},
}

var (
	preferredPort int
	rootDir       string
	pingMu        sync.Mutex
	lastPing      = time.Now()
	listenAddr    string
	saveMu        sync.Mutex
)

func (g *group) dir() string  { return filepath.Join(rootDir, g.sub) }
func (g *group) file() string { return filepath.Join(g.dir(), g.dataName) }

func findGroup(id string) *group {
	for _, g := range groups {
		if g.id == id {
			return g
		}
	}
	return nil
}

func main() {
	if p, err := strconv.Atoi(portText); err == nil {
		preferredPort = p
	} else {
		preferredPort = 47850
	}
	docs := documentsDir()
	rootDir = filepath.Join(docs, folderName)
	if err := os.MkdirAll(rootDir, 0o755); err != nil {
		fatal("No se pudo crear la carpeta de datos:\n" + rootDir + "\n\n" + err.Error())
	}
	if lf, err := os.OpenFile(filepath.Join(rootDir, "kenti.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644); err == nil {
		log.SetOutput(lf)
		defer lf.Close()
	}
	for _, g := range groups {
		if err := os.MkdirAll(g.dir(), 0o755); err != nil {
			fatal("No se pudo crear la carpeta de datos:\n" + g.dir() + "\n\n" + err.Error())
		}
		importLegacy(docs, g)
	}

	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", preferredPort))
	if err != nil {
		// ¿Ya hay un Kenti abierto? Entonces sólo abrimos otra ventana.
		if kentiRunning(preferredPort) {
			log.Println("Kenti ya estaba abierto; se abre otra ventana")
			openWindow(fmt.Sprintf("http://127.0.0.1:%d/", preferredPort))
			return
		}
		ln, err = net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			fatal("Kenti no pudo iniciar su servidor local.\n\n" + err.Error())
		}
	}
	listenAddr = ln.Addr().String()
	url := "http://" + listenAddr + "/"

	srv := &http.Server{Handler: routes(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		if err := srv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Println("servidor:", err)
		}
	}()
	log.Printf("%s %s en %s · datos: %s", appName, version, url, rootDir)

	if done := openWindow(url); done != nil {
		<-done // la ventana se cerró
		time.Sleep(1200 * time.Millisecond)
	} else {
		// Navegador predeterminado: se cierra tras 3 minutos sin señales de la página.
		for {
			time.Sleep(30 * time.Second)
			pingMu.Lock()
			idle := time.Since(lastPing)
			pingMu.Unlock()
			if idle > 3*time.Minute {
				break
			}
		}
	}
	log.Println("Kenti se cerró")
}

// importLegacy copia (sin tocar el original) los datos que el módulo suelto
// dejó en Documentos\Kenti <Grupo>, si esta especialidad todavía no tiene datos.
func importLegacy(docs string, g *group) {
	if g.legacy == "" {
		return
	}
	if _, err := os.Stat(g.file()); err == nil {
		return
	}
	old := filepath.Join(docs, g.legacy, g.dataName)
	b, err := os.ReadFile(old)
	if err != nil || len(b) == 0 || !json.Valid(b) {
		return
	}
	if err := writeAtomic(g.file(), b); err != nil {
		log.Println("importar", old, err)
		return
	}
	log.Println("datos importados de", old)
}

func kentiRunning(port int) bool {
	c := http.Client{Timeout: 2 * time.Second}
	r, err := c.Get(fmt.Sprintf("http://127.0.0.1:%d/api/info", port))
	if err != nil {
		return false
	}
	defer r.Body.Close()
	var info map[string]any
	return json.NewDecoder(r.Body).Decode(&info) == nil && info["app"] == appID
}

func touchPing() {
	pingMu.Lock()
	lastPing = time.Now()
	pingMu.Unlock()
}

func routes() http.Handler {
	sub, _ := fs.Sub(webFS, "web")
	static := http.FileServer(http.FS(sub))
	mux := http.NewServeMux()

	// ---- globales (pantalla de inicio) ----
	mux.HandleFunc("/api/info", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]any{"app": appID, "version": version, "carpeta": rootDir})
	})
	mux.HandleFunc("/api/ping", func(w http.ResponseWriter, r *http.Request) {
		touchPing()
		writeJSON(w, map[string]any{"ok": true})
	})
	mux.HandleFunc("/api/estado", func(w http.ResponseWriter, r *http.Request) {
		out := map[string]any{}
		for _, g := range groups {
			e := map[string]any{"datos": false}
			if st, err := os.Stat(g.file()); err == nil && st.Size() > 0 {
				e["datos"] = true
				e["modificado"] = st.ModTime().Format(time.RFC3339)
			}
			out[g.id] = e
		}
		writeJSON(w, map[string]any{"carpeta": rootDir, "version": version, "grupos": out})
	})
	mux.HandleFunc("/api/abrir-carpeta", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || !trusted(r) {
			http.Error(w, "no permitido", http.StatusForbidden)
			return
		}
		openFolder(rootDir)
		writeJSON(w, map[string]any{"ok": true})
	})

	// ---- una especialidad: /g/<id>/ y /g/<id>/api/... ----
	mux.HandleFunc("/g/", func(w http.ResponseWriter, r *http.Request) {
		rest := strings.TrimPrefix(r.URL.Path, "/g/")
		id, tail, _ := strings.Cut(rest, "/")
		g := findGroup(id)
		if g == nil {
			http.NotFound(w, r)
			return
		}
		switch {
		case tail == "" && !strings.HasSuffix(r.URL.Path, "/"):
			http.Redirect(w, r, "/g/"+id+"/", http.StatusFound)
		case tail == "":
			b, err := fs.ReadFile(sub, "g/"+id+".html")
			if err != nil {
				http.NotFound(w, r)
				return
			}
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.Write(b)
		case strings.HasPrefix(tail, "api/"):
			g.api(w, r, strings.TrimPrefix(tail, "api/"))
		default:
			http.NotFound(w, r)
		}
	})
	mux.Handle("/", static)

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Sólo se atiende a esta máquina con su propio nombre de host (evita DNS rebinding).
		if !localHost(r.Host) {
			http.Error(w, "host no permitido", http.StatusForbidden)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		mux.ServeHTTP(w, r)
	})
}

// api atiende lo que cada especialidad pide a su servidor: sus datos, su
// carpeta y sus exportaciones, siempre dentro de su subcarpeta.
func (g *group) api(w http.ResponseWriter, r *http.Request, what string) {
	switch what {
	case "info":
		writeJSON(w, map[string]any{"app": g.appID, "version": version, "carpeta": g.dir(), "archivo": g.file()})
	case "ping":
		touchPing()
		writeJSON(w, map[string]any{"ok": true})
	case "datos":
		switch r.Method {
		case http.MethodGet:
			b, err := os.ReadFile(g.file())
			if errors.Is(err, os.ErrNotExist) {
				w.WriteHeader(http.StatusNoContent) // todavía no hay datos guardados
				return
			} else if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.Write(b)
		case http.MethodPut, http.MethodPost:
			if !trusted(r) {
				http.Error(w, "origen no permitido", http.StatusForbidden)
				return
			}
			b, err := io.ReadAll(io.LimitReader(r.Body, 64<<20))
			if err != nil || !json.Valid(b) {
				http.Error(w, "datos inválidos", http.StatusBadRequest)
				return
			}
			if err := g.save(b); err != nil {
				log.Println("guardar", g.id, err)
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			writeJSON(w, map[string]any{"ok": true})
		default:
			http.Error(w, "método no permitido", http.StatusMethodNotAllowed)
		}
	case "taxon":
		if !trusted(r) {
			http.Error(w, "origen no permitido", http.StatusForbidden)
			return
		}
		writeJSON(w, taxonLookup(r.URL.Query().Get("nombre"), r.URL.Query().Get("genero"), r.URL.Query().Get("especie")))
	case "exportar":
		// El Excel lo arma la página; el programa sólo lo guarda en la carpeta de la especialidad.
		if r.Method != http.MethodPost || !trusted(r) {
			http.Error(w, "no permitido", http.StatusForbidden)
			return
		}
		b, err := io.ReadAll(io.LimitReader(r.Body, 256<<20))
		if err != nil || len(b) == 0 {
			http.Error(w, "no llegó el archivo", http.StatusBadRequest)
			return
		}
		name := safeName(r.URL.Query().Get("nombre"))
		if name == "" {
			name = "Kenti " + g.nombre
		}
		final := name + ".xlsx"
		path := filepath.Join(g.dir(), final)
		for i := 2; i < 200; i++ {
			if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
				break
			}
			final = fmt.Sprintf("%s (%d).xlsx", name, i)
			path = filepath.Join(g.dir(), final)
		}
		saveMu.Lock()
		err = writeAtomic(path, b)
		saveMu.Unlock()
		if err != nil {
			log.Println("exportar", g.id, err)
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, map[string]any{"ok": true, "nombre": final, "carpeta": g.dir()})
	case "abrir-exportacion":
		if r.Method != http.MethodPost || !trusted(r) {
			http.Error(w, "no permitido", http.StatusForbidden)
			return
		}
		var q struct{ Nombre, Modo string }
		json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&q)
		name := safeName(strings.TrimSuffix(q.Nombre, ".xlsx"))
		if name == "" {
			http.Error(w, "nombre inválido", http.StatusBadRequest)
			return
		}
		if q.Modo == "abrir" {
			openFile(filepath.Join(g.dir(), name+".xlsx"))
		} else {
			openFolder(g.dir())
		}
		writeJSON(w, map[string]any{"ok": true})
	case "abrir-carpeta":
		if r.Method != http.MethodPost || !trusted(r) {
			http.Error(w, "no permitido", http.StatusForbidden)
			return
		}
		openFolder(g.dir())
		writeJSON(w, map[string]any{"ok": true})
	default:
		http.NotFound(w, r)
	}
}

func (g *group) save(b []byte) error {
	g.mu.Lock()
	defer g.mu.Unlock()
	// Una copia de respaldo del archivo anterior, una vez por sesión.
	if !g.backedUp {
		if old, err := os.ReadFile(g.file()); err == nil && len(old) > 0 {
			_ = os.WriteFile(filepath.Join(g.dir(), strings.TrimSuffix(g.dataName, ".json")+".respaldo.json"), old, 0o644)
		}
		g.backedUp = true
	}
	var pretty bytes.Buffer
	if err := json.Indent(&pretty, b, "", "  "); err != nil {
		return err
	}
	return writeAtomic(g.file(), pretty.Bytes())
}

var nameBad = regexp.MustCompile(`[^\p{L}\p{N} ._()-]+`)

// safeName deja un nombre de archivo sin rutas ni caracteres raros.
func safeName(s string) string {
	s = strings.TrimSpace(nameBad.ReplaceAllString(s, " "))
	s = strings.Trim(strings.Join(strings.Fields(s), " "), " .")
	if len(s) > 120 {
		s = strings.TrimSpace(s[:120])
	}
	return s
}

func localHost(host string) bool {
	h, _, err := net.SplitHostPort(host)
	if err != nil {
		h = host
	}
	return h == "127.0.0.1" || h == "localhost"
}

// trusted exige la cabecera propia de Kenti: un sitio web ajeno no puede
// enviarla sin una verificación CORS que este servidor nunca aprueba.
func trusted(r *http.Request) bool {
	if r.Header.Get("X-Kenti") != "1" {
		return false
	}
	if o := r.Header.Get("Origin"); o != "" && !strings.HasPrefix(o, "http://127.0.0.1:") && !strings.HasPrefix(o, "http://localhost:") {
		return false
	}
	return true
}

func writeAtomic(path string, b []byte) error {
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, b, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(v)
}
