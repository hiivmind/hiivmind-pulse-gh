# Actions

GitHub Actions documentation - CI/CD, workflows, runners, and automation.

> **239 files** | Source: `docs:actions/`

---

## Getting Started

- **Understanding GitHub Actions** `docs:actions/get-started/understand-github-actions.md` - Core concepts and terminology
- **Quickstart** `docs:actions/get-started/quickstart.md` - Create your first workflow
- **Continuous Integration** `docs:actions/get-started/continuous-integration.md` - CI with GitHub Actions
- **Continuous Deployment** `docs:actions/get-started/continuous-deployment.md` - CD pipelines
- **Actions vs Apps** `docs:actions/get-started/actions-vs-apps.md` - When to use Actions vs GitHub Apps

---

## Concepts

### Workflows and Actions

- **Workflows** `docs:actions/concepts/workflows-and-actions/workflows.md` - Workflow fundamentals
- **Custom Actions** `docs:actions/concepts/workflows-and-actions/custom-actions.md` - Creating reusable actions
- **Contexts** `docs:actions/concepts/workflows-and-actions/contexts.md` - Accessing context information
- **Expressions** `docs:actions/concepts/workflows-and-actions/expressions.md` - Expression syntax
- **Variables** `docs:actions/concepts/workflows-and-actions/variables.md` - Environment and workflow variables
- **Secrets** `docs:actions/concepts/security/secrets.md` - Managing secrets
- **Concurrency** `docs:actions/concepts/workflows-and-actions/concurrency.md` - Controlling concurrent workflows
- **Dependency Caching** `docs:actions/concepts/workflows-and-actions/dependency-caching.md` - Caching dependencies
- **Workflow Artifacts** `docs:actions/concepts/workflows-and-actions/workflow-artifacts.md` - Storing artifacts
- **Deployment Environments** `docs:actions/concepts/workflows-and-actions/deployment-environments.md` - Environment protection
- **Reusing Configurations** `docs:actions/concepts/workflows-and-actions/reusing-workflow-configurations.md` - Reusable workflows

### Runners

- **GitHub-Hosted Runners** `docs:actions/concepts/runners/github-hosted-runners.md` - Using GitHub's runners
- **Self-Hosted Runners** `docs:actions/concepts/runners/self-hosted-runners.md` - Running your own
- **Larger Runners** `docs:actions/concepts/runners/larger-runners.md` - High-performance runners
- **Runner Groups** `docs:actions/concepts/runners/runner-groups.md` - Organizing runners
- **Runner Scale Sets** `docs:actions/concepts/runners/runner-scale-sets.md` - Kubernetes scaling
- **Actions Runner Controller** `docs:actions/concepts/runners/actions-runner-controller.md` - ARC overview
- **Private Networking** `docs:actions/concepts/runners/private-networking.md` - Network configuration

### Security

- **GITHUB_TOKEN** `docs:actions/concepts/security/github_token.md` - Automatic authentication
- **OpenID Connect** `docs:actions/concepts/security/openid-connect.md` - OIDC for cloud auth
- **Secrets** `docs:actions/concepts/security/secrets.md` - Secret management
- **Artifact Attestations** `docs:actions/concepts/security/artifact-attestations.md` - Supply chain security
- **Script Injections** `docs:actions/concepts/security/script-injections.md` - Avoiding injection attacks
- **Compromised Runners** `docs:actions/concepts/security/compromised-runners.md` - Security hardening

---

## Reference

### Workflow Syntax

- **Workflow Syntax** `docs:actions/reference/workflows-and-actions/workflow-syntax.md` - Complete YAML reference
- **Events that Trigger Workflows** `docs:actions/reference/workflows-and-actions/events-that-trigger-workflows.md` - All trigger events
- **Contexts Reference** `docs:actions/reference/workflows-and-actions/contexts.md` - Context object reference
- **Expressions Reference** `docs:actions/reference/workflows-and-actions/expressions.md` - Expression functions
- **Variables Reference** `docs:actions/reference/workflows-and-actions/variables.md` - Variable reference
- **Workflow Commands** `docs:actions/reference/workflows-and-actions/workflow-commands.md` - Commands for runners
- **Metadata Syntax** `docs:actions/reference/workflows-and-actions/metadata-syntax.md` - action.yml reference
- **Dockerfile Support** `docs:actions/reference/workflows-and-actions/dockerfile-support.md` - Docker actions

### Runner Reference

- **GitHub-Hosted Runners** `docs:actions/reference/runners/github-hosted-runners.md` - Specs and software
- **Larger Runners** `docs:actions/reference/runners/larger-runners.md` - Large runner specs
- **Self-Hosted Runners** `docs:actions/reference/runners/self-hosted-runners.md` - Self-hosted reference

### Security Reference

- **OIDC Reference** `docs:actions/reference/security/oidc.md` - OIDC claims and configuration
- **Secrets Reference** `docs:actions/reference/security/secrets.md` - Secret limits and usage
- **Secure Use** `docs:actions/reference/security/secure-use.md` - Security best practices

### Limits

- **Usage Limits** `docs:actions/reference/limits.md` - Rate limits and quotas

---

## How-Tos

### Writing Workflows

- **Trigger a Workflow** `docs:actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow.md`
- **Control with Conditions** `docs:actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions.md`
- **Control Concurrency** `docs:actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency.md`
- **Use Jobs** `docs:actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs.md`
- **Pass Job Outputs** `docs:actions/how-tos/write-workflows/choose-what-workflows-do/pass-job-outputs.md`
- **Run Job Variations** `docs:actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations.md` - Matrix builds
- **Use Secrets** `docs:actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets.md`
- **Use Variables** `docs:actions/how-tos/write-workflows/choose-what-workflows-do/use-variables.md`
- **Choose Runner** `docs:actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job.md`
- **Run in Container** `docs:actions/how-tos/write-workflows/choose-where-workflows-run/run-jobs-in-a-container.md`
- **Use Workflow Templates** `docs:actions/how-tos/write-workflows/use-workflow-templates.md`

### Managing Runners

#### GitHub-Hosted

- **Use GitHub-Hosted Runners** `docs:actions/how-tos/manage-runners/github-hosted-runners/use-github-hosted-runners.md`
- **Customize Runners** `docs:actions/how-tos/manage-runners/github-hosted-runners/customize-runners.md`
- **Connect to Private Network** `docs:actions/how-tos/manage-runners/github-hosted-runners/connect-to-a-private-network/index.md`

#### Self-Hosted

- **Add Runners** `docs:actions/how-tos/manage-runners/self-hosted-runners/add-runners.md`
- **Configure Application** `docs:actions/how-tos/manage-runners/self-hosted-runners/configure-the-application.md`
- **Apply Labels** `docs:actions/how-tos/manage-runners/self-hosted-runners/apply-labels.md`
- **Manage Access** `docs:actions/how-tos/manage-runners/self-hosted-runners/manage-access.md`
- **Monitor and Troubleshoot** `docs:actions/how-tos/manage-runners/self-hosted-runners/monitor-and-troubleshoot.md`
- **Remove Runners** `docs:actions/how-tos/manage-runners/self-hosted-runners/remove-runners.md`

#### Larger Runners

- **Manage Larger Runners** `docs:actions/how-tos/manage-runners/larger-runners/manage-larger-runners.md`
- **Control Access** `docs:actions/how-tos/manage-runners/larger-runners/control-access.md`
- **Use Custom Images** `docs:actions/how-tos/manage-runners/larger-runners/use-custom-images.md`

### Managing Workflow Runs

- **Manually Run** `docs:actions/how-tos/manage-workflow-runs/manually-run-a-workflow.md`
- **Re-run Workflows** `docs:actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs.md`
- **Cancel Run** `docs:actions/how-tos/manage-workflow-runs/cancel-a-workflow-run.md`
- **Skip Runs** `docs:actions/how-tos/manage-workflow-runs/skip-workflow-runs.md`
- **Download Artifacts** `docs:actions/how-tos/manage-workflow-runs/download-workflow-artifacts.md`
- **Manage Caches** `docs:actions/how-tos/manage-workflow-runs/manage-caches.md`
- **Approve Fork Runs** `docs:actions/how-tos/manage-workflow-runs/approve-runs-from-forks.md`

### Monitoring

- **View Run History** `docs:actions/how-tos/monitor-workflows/view-workflow-run-history.md`
- **Use Run Logs** `docs:actions/how-tos/monitor-workflows/use-workflow-run-logs.md`
- **Enable Debug Logging** `docs:actions/how-tos/monitor-workflows/enable-debug-logging.md`
- **Add Status Badge** `docs:actions/how-tos/monitor-workflows/add-a-status-badge.md`

### Deployments

- **Manage Environments** `docs:actions/how-tos/deploy/configure-and-manage-deployments/manage-environments.md`
- **Review Deployments** `docs:actions/how-tos/deploy/configure-and-manage-deployments/review-deployments.md`
- **Custom Protection Rules** `docs:actions/how-tos/deploy/configure-and-manage-deployments/create-custom-protection-rules.md`

#### Deploy to Platforms

- **Amazon ECS** `docs:actions/how-tos/deploy/deploy-to-third-party-platforms/amazon-elastic-container-service.md`
- **Azure Kubernetes** `docs:actions/how-tos/deploy/deploy-to-third-party-platforms/azure-kubernetes-service.md`
- **Google Kubernetes** `docs:actions/how-tos/deploy/deploy-to-third-party-platforms/google-kubernetes-engine.md`
- **Azure App Service (Docker)** `docs:actions/how-tos/deploy/deploy-to-third-party-platforms/docker-to-azure-app-service.md`
- **Azure App Service (Node.js)** `docs:actions/how-tos/deploy/deploy-to-third-party-platforms/nodejs-to-azure-app-service.md`
- **Azure App Service (Python)** `docs:actions/how-tos/deploy/deploy-to-third-party-platforms/python-to-azure-app-service.md`

### Security Hardening

#### OIDC Authentication

- **OIDC in AWS** `docs:actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws.md`
- **OIDC in Azure** `docs:actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure.md`
- **OIDC in GCP** `docs:actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-google-cloud-platform.md`
- **OIDC in HashiCorp Vault** `docs:actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-hashicorp-vault.md`
- **OIDC in PyPI** `docs:actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-pypi.md`

#### Artifact Attestations

- **Use Attestations** `docs:actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations.md`
- **Enforce Attestations** `docs:actions/how-tos/secure-your-work/use-artifact-attestations/enforce-artifact-attestations.md`
- **Verify Offline** `docs:actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline.md`

### Reusing Automations

- **Reuse Workflows** `docs:actions/how-tos/reuse-automations/reuse-workflows.md`
- **Create Workflow Templates** `docs:actions/how-tos/reuse-automations/create-workflow-templates.md`
- **Share with Organization** `docs:actions/how-tos/reuse-automations/share-with-your-organization.md`
- **Share with Enterprise** `docs:actions/how-tos/reuse-automations/share-with-your-enterprise.md`

### Creating Actions

- **Create JavaScript Action** `docs:actions/tutorials/create-actions/create-a-javascript-action.md`
- **Create Composite Action** `docs:actions/tutorials/create-actions/create-a-composite-action.md`
- **Create Docker Action** `docs:actions/tutorials/use-containerized-services/create-a-docker-container-action.md`
- **Publish to Marketplace** `docs:actions/how-tos/create-and-publish-actions/publish-in-github-marketplace.md`
- **Release and Maintain** `docs:actions/how-tos/create-and-publish-actions/release-and-maintain-actions.md`

---

## Tutorials

### Build and Test

- **Node.js** `docs:actions/tutorials/build-and-test-code/nodejs.md`
- **Python** `docs:actions/tutorials/build-and-test-code/python.md`
- **Java (Maven)** `docs:actions/tutorials/build-and-test-code/java-with-maven.md`
- **Java (Gradle)** `docs:actions/tutorials/build-and-test-code/java-with-gradle.md`
- **.NET** `docs:actions/tutorials/build-and-test-code/net.md`
- **Go** `docs:actions/tutorials/build-and-test-code/go.md`
- **Ruby** `docs:actions/tutorials/build-and-test-code/ruby.md`
- **Rust** `docs:actions/tutorials/build-and-test-code/rust.md`
- **Swift** `docs:actions/tutorials/build-and-test-code/swift.md`

### Publish Packages

- **Docker Images** `docs:actions/tutorials/publish-packages/publish-docker-images.md`
- **Node.js Packages** `docs:actions/tutorials/publish-packages/publish-nodejs-packages.md`
- **Java (Maven)** `docs:actions/tutorials/publish-packages/publish-java-packages-with-maven.md`
- **Java (Gradle)** `docs:actions/tutorials/publish-packages/publish-java-packages-with-gradle.md`

### Service Containers

- **PostgreSQL** `docs:actions/tutorials/use-containerized-services/create-postgresql-service-containers.md`
- **Redis** `docs:actions/tutorials/use-containerized-services/create-redis-service-containers.md`

### Actions Runner Controller (ARC)

- **ARC Quickstart** `docs:actions/tutorials/use-actions-runner-controller/quickstart.md`
- **Deploy Runner Scale Sets** `docs:actions/tutorials/use-actions-runner-controller/deploy-runner-scale-sets.md`
- **Authenticate to API** `docs:actions/tutorials/use-actions-runner-controller/authenticate-to-the-api.md`
- **Use in Workflow** `docs:actions/tutorials/use-actions-runner-controller/use-arc-in-a-workflow.md`
- **Troubleshoot ARC** `docs:actions/tutorials/use-actions-runner-controller/troubleshoot.md`

### Migrate to GitHub Actions

- **Use GitHub Actions Importer** `docs:actions/tutorials/migrate-to-github-actions/automated-migrations/use-github-actions-importer.md`
- **From Jenkins** `docs:actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-jenkins.md`
- **From GitLab CI/CD** `docs:actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-gitlab-cicd.md`
- **From CircleCI** `docs:actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-circleci.md`
- **From Azure Pipelines** `docs:actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-azure-pipelines.md`
- **From Travis CI** `docs:actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-travis-ci.md`

---

## Troubleshooting

- **Troubleshoot Workflows** `docs:actions/how-tos/troubleshoot-workflows.md`
- **Get Support** `docs:actions/how-tos/get-support.md`
