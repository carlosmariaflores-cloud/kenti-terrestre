package main

// Consulta de clasificación en línea. La hace el lanzador y no la página: evita
// el bloqueo entre orígenes, pone tiempo máximo y deja un único lugar donde
// cambiar la fuente si algún día se suma otra.

import (
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const taxFuente = "gbif"

var taxClient = &http.Client{Timeout: 15 * time.Second}

type taxResp struct {
	Nombre   string `json:"nombre"`
	Fuente   string `json:"fuente"`
	Match    string `json:"match"` // exacta · genero · ninguna
	Aceptado string `json:"aceptado"`
	Autor    string `json:"autor"`
	Estado   string `json:"estado"`
	Reino    string `json:"reino"`
	Division string `json:"division"`
	Clase    string `json:"clase"`
	Orden    string `json:"orden"`
	Familia  string `json:"familia"`
	Genero   string `json:"genero"`
	Error    bool   `json:"error,omitempty"`
	Mensaje  string `json:"mensaje,omitempty"`
}

type gbifMatch struct {
	MatchType     string `json:"matchType"`
	CanonicalName string `json:"canonicalName"`
	Scientific    string `json:"scientificName"`
	Status        string `json:"status"`
	Kingdom       string `json:"kingdom"`
	Phylum        string `json:"phylum"`
	Class         string `json:"class"`
	Order         string `json:"order"`
	Family        string `json:"family"`
	Genus         string `json:"genus"`
}

func (m gbifMatch) ok() bool { return m.MatchType == "EXACT" || m.MatchType == "FUZZY" }

func gbifQuery(name string, rankGenus bool, kingdom string) (gbifMatch, error) {
	var m gbifMatch
	q := url.Values{}
	q.Set("name", name)
	if rankGenus {
		q.Set("rank", "GENUS")
	}
	if kingdom != "" {
		q.Set("kingdom", kingdom)
	}
	req, err := http.NewRequest("GET", "https://api.gbif.org/v1/species/match?"+q.Encode(), nil)
	if err != nil {
		return m, err
	}
	req.Header.Set("User-Agent", "Kenti/"+version+" (monitoreo ambiental)")
	res, err := taxClient.Do(req)
	if err != nil {
		return m, err
	}
	defer res.Body.Close()
	if res.StatusCode != 200 {
		return m, errStatus(res.StatusCode)
	}
	err = json.NewDecoder(res.Body).Decode(&m)
	return m, err
}

type statusErr int

func (e statusErr) Error() string { return "GBIF respondió " + http.StatusText(int(e)) }
func errStatus(c int) error       { return statusErr(c) }

// Los géneros de algas se repiten entre reinos: GBIF necesita el reino para no
// devolver un insecto o una planta con el mismo nombre.
var reinos = []string{"Chromista", "Plantae", "Bacteria", "Protozoa"}

func taxonLookup(nombre, genero, especie string) taxResp {
	nombre = strings.TrimSpace(nombre)
	if nombre == "" {
		return taxResp{Error: true, Mensaje: "consulta vacía"}
	}
	out := taxResp{Nombre: nombre, Fuente: taxFuente, Match: "ninguna"}
	llena := func(m gbifMatch, match string) taxResp {
		out.Match = match
		out.Aceptado = m.CanonicalName
		out.Autor = m.Scientific
		out.Estado = m.Status
		out.Reino = m.Kingdom
		out.Division = m.Phylum
		out.Clase = m.Class
		out.Orden = m.Order
		out.Familia = m.Family
		out.Genero = m.Genus
		return out
	}
	if strings.TrimSpace(especie) != "" {
		m, err := gbifQuery(nombre, false, "")
		if err != nil {
			return taxResp{Error: true, Mensaje: err.Error()}
		}
		if m.ok() {
			return llena(m, "exacta")
		}
	}
	// Sin especie, o sin coincidencia: se prueba el género, reino por reino.
	g := strings.TrimSpace(genero)
	if g == "" {
		g = strings.Fields(nombre)[0]
	}
	var ultimo error
	for _, reino := range reinos {
		m, err := gbifQuery(g, true, reino)
		if err != nil {
			ultimo = err
			continue
		}
		if m.ok() && m.Genus != "" {
			return llena(m, "genero")
		}
	}
	if ultimo != nil {
		return taxResp{Error: true, Mensaje: ultimo.Error()}
	}
	return out
}
