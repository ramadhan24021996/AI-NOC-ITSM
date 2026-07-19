package topology

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"go_incident_analysis/SERVER/go_core/database"
)

type Handler struct {
	db *gorm.DB
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{db: db}
}

func (h *Handler) RegisterRoutes(r *gin.Engine) {
	r.GET("/api/fleet/admin/topology", h.GetTopology)
}

func (h *Handler) GetTopology(c *gin.Context) {
	var sites []database.FleetSite
	if err := h.db.Order("site_name ASC").Find(&sites).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
		return
	}

	var devices []database.FleetDevice
	if err := h.db.Where("site_id IS NOT NULL").Find(&devices).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
		return
	}

	var printers []database.FleetPrinter
	if err := h.db.Where("site_id IS NOT NULL").Find(&printers).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
		return
	}

	type deviceTopology struct {
		PCName   string                 `json:"pc_name"`
		SiteID   string                 `json:"site_id"`
		Status   string                 `json:"status"`
		Printers []database.FleetPrinter `json:"printers"`
	}

	type siteTopology struct {
		database.FleetSite
		Devices          []deviceTopology        `json:"devices"`
		UnlinkedPrinters []database.FleetPrinter `json:"unlinked_printers"`
	}

	var topology []siteTopology

	for _, s := range sites {
		st := siteTopology{
			FleetSite:        s,
			Devices:          []deviceTopology{},
			UnlinkedPrinters: []database.FleetPrinter{},
		}

		// Filter printers for this site
		var sitePrinters []database.FleetPrinter
		for _, p := range printers {
			if p.SiteID != nil && *p.SiteID == s.SiteID {
				sitePrinters = append(sitePrinters, p)
			}
		}

		// Filter devices for this site
		for _, d := range devices {
			if d.SiteID != nil && *d.SiteID == s.SiteID {
				dt := deviceTopology{
					PCName:   d.PCName,
					SiteID:   *d.SiteID,
					Status:   d.Status,
					Printers: []database.FleetPrinter{},
				}

				// Assign printers to this PC
				for _, p := range sitePrinters {
					if p.PCName != nil && *p.PCName == d.PCName {
						dt.Printers = append(dt.Printers, p)
					}
				}

				st.Devices = append(st.Devices, dt)
			}
		}

		// Unlinked printers
		for _, p := range sitePrinters {
			if p.PCName == nil || *p.PCName == "" {
				st.UnlinkedPrinters = append(st.UnlinkedPrinters, p)
			}
		}

		topology = append(topology, st)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "topology": topology})
}
