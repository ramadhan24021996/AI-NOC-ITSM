package incident

import (
	"context"
	"time"

	"gorm.io/gorm"
	"go_incident_analysis/SERVER/go_core/database"
	"go_incident_analysis/portal/dashboard/core"
)

type Repository interface {
	GetIncidents(ctx context.Context) ([]core.FleetIncident, error)
	GetIncidentByID(ctx context.Context, id uint) (core.FleetIncident, error)
	CreateIncident(ctx context.Context, incident *core.FleetIncident) error
	UpdateIncidentStatus(ctx context.Context, id uint, status string) error
	GetSites(ctx context.Context) ([]database.FleetSite, error)
	CreateSite(ctx context.Context, site *database.FleetSite) error
	DeleteSite(ctx context.Context, siteID string) error
	GetDevices(ctx context.Context) ([]database.FleetDevice, error)
	CreateDevice(ctx context.Context, device *database.FleetDevice) error
	DeleteDevice(ctx context.Context, pcName string) error
}

type sqlRepository struct {
	db *gorm.DB
}

func NewRepository(db *gorm.DB) Repository {
	return &sqlRepository{db: db}
}

func (r *sqlRepository) GetIncidents(ctx context.Context) ([]core.FleetIncident, error) {
	var incidents []core.FleetIncident
	err := r.db.WithContext(ctx).Order("created_at DESC").Find(&incidents).Error
	return incidents, err
}

func (r *sqlRepository) GetIncidentByID(ctx context.Context, id uint) (core.FleetIncident, error) {
	var inc core.FleetIncident
	err := r.db.WithContext(ctx).First(&inc, id).Error
	return inc, err
}

func (r *sqlRepository) CreateIncident(ctx context.Context, incident *core.FleetIncident) error {
	return r.db.WithContext(ctx).Create(incident).Error
}

func (r *sqlRepository) UpdateIncidentStatus(ctx context.Context, id uint, status string) error {
	now := time.Now()
	updates := map[string]interface{}{"status": status}
	if status == "RESOLVED" || status == "SUCCESS" {
		updates["resolved_at"] = &now
	}
	return r.db.WithContext(ctx).Model(&core.FleetIncident{}).Where("incident_id = ?", id).Updates(updates).Error
}

func (r *sqlRepository) GetSites(ctx context.Context) ([]database.FleetSite, error) {
	var sites []database.FleetSite
	err := r.db.WithContext(ctx).Order("site_name ASC").Find(&sites).Error
	return sites, err
}

func (r *sqlRepository) CreateSite(ctx context.Context, site *database.FleetSite) error {
	return r.db.WithContext(ctx).Create(site).Error
}

func (r *sqlRepository) DeleteSite(ctx context.Context, siteID string) error {
	return r.db.WithContext(ctx).Where("site_id = ?", siteID).Delete(&database.FleetSite{}).Error
}

func (r *sqlRepository) GetDevices(ctx context.Context) ([]database.FleetDevice, error) {
	var devices []database.FleetDevice
	err := r.db.WithContext(ctx).Find(&devices).Error
	return devices, err
}

func (r *sqlRepository) CreateDevice(ctx context.Context, device *database.FleetDevice) error {
	return r.db.WithContext(ctx).Create(device).Error
}

func (r *sqlRepository) DeleteDevice(ctx context.Context, pcName string) error {
	return r.db.WithContext(ctx).Where("pc_name = ?", pcName).Delete(&database.FleetDevice{}).Error
}
