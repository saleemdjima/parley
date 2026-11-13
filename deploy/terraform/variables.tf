variable "project_id" {
  type        = string
  description = "GCP project ID (personal account, not Lycaon)."
}

variable "region" {
  type        = string
  default     = "europe-west1"
  description = "Region for Artifact Registry and Cloud Run."
}

variable "service_name" {
  type        = string
  default     = "parley"
  description = "Cloud Run service name."
}

variable "repository_id" {
  type        = string
  default     = "parley"
  description = "Artifact Registry Docker repository ID."
}

variable "github_repository" {
  type        = string
  default     = "saleemdjima/parley"
  description = "owner/repo allowed to deploy via Workload Identity Federation."
}

variable "parquet_path" {
  type        = string
  default     = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
  description = "Parquet source the running service queries."
}

variable "allow_unauthenticated" {
  type        = bool
  default     = false
  description = "Expose the Cloud Run service publicly. Keep false unless you want recruiters to curl it directly; /documents is only guarded by API_KEY."
}

variable "min_instances" {
  type        = number
  default     = 0
  description = "0 scales to zero (free when idle, ~2-3s cold start)."
}

variable "max_instances" {
  type        = number
  default     = 2
  description = "Cap concurrency cost for a demo."
}
