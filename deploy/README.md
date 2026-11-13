# Deploying parley

Infrastructure is Terraform; deploys are GitHub Actions. CI authenticates to GCP
with **Workload Identity Federation** (keyless OIDC) -- no service-account key is
stored anywhere, which is what makes this safe for a public repo.

All commands below are yours to run (personal account, not Lycaon).

## One-time setup

### 1. Terraform state bucket (chicken-and-egg: the GCS backend needs a bucket first)

```bash
PROJECT=gen-lang-client-0522229727
gcloud storage buckets create gs://${PROJECT}-tfstate \
  --project=$PROJECT --location=europe-west1 --uniform-bucket-level-access
gcloud storage buckets update gs://${PROJECT}-tfstate --versioning
```

### 2. Init + configure

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars   # edit if needed
terraform init -backend-config="bucket=${PROJECT}-tfstate"
```

### 3. Apply in two phases (keeps secret values out of Terraform state)

Cloud Run references `latest` of each secret, so a version must exist before it
deploys. Create the secret *containers* first, seed them, then apply the rest.

```bash
# Phase A: secret containers (and the APIs they need)
terraform apply -target=google_secret_manager_secret.app

# Seed the values (never stored in Terraform):
printf '%s' 'YOUR_GEMINI_KEY'  | gcloud secrets versions add google-api-key --data-file=-
printf '%s' 'YOUR_API_KEY'     | gcloud secrets versions add api-key        --data-file=-

# Phase B: everything else (WIF, Cloud Run, IAM)
terraform apply
```

### 4. Wire the GitHub repo variables (not secrets -- none of these are sensitive)

```bash
terraform output
```

In GitHub: **Settings -> Secrets and variables -> Actions -> Variables**, add:

| Variable | Value (from `terraform output`) |
|---|---|
| `WIF_PROVIDER` | `workload_identity_provider` |
| `DEPLOY_SERVICE_ACCOUNT` | `deployer_service_account` |
| `AR_REPO` | `artifact_registry` |
| `REGION` | `region` |
| `SERVICE_NAME` | `service_name` |

## Deploying

Push to `main`. CI runs lint + mypy + tests on every PR (no cloud access), and on
`main` it also builds the image, pushes it to Artifact Registry, and deploys to
Cloud Run -- authenticating via WIF, reading the build-time Gemini key straight
from Secret Manager.

## Notes

- **Public exposure** is off by default (`allow_unauthenticated = false`). Flip the
  tfvar to `true` only when you want recruiters to curl the service; `/documents`
  is a write endpoint guarded only by `API_KEY`.
- **Fork PRs** can't reach any of this: the deploy job only runs on `push` to
  `main`, and GitHub never exposes OIDC/secrets to pull requests from forks.
- To stop overnight billing, scale to zero: it already defaults to
  `min_instances = 0`.
