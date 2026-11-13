output "workload_identity_provider" {
  description = "Set as repo variable WIF_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "Set as repo variable DEPLOY_SERVICE_ACCOUNT."
  value       = google_service_account.deployer.email
}

output "artifact_registry" {
  description = "Set as repo variable AR_REPO (host/project/repo)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository_id}"
}

output "region" {
  value = var.region
}

output "service_name" {
  value = var.service_name
}

output "service_url" {
  value = google_cloud_run_v2_service.parley.uri
}
