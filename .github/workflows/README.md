# GitHub Actions Workflows

This directory contains automated workflows for the CAMS Utilities project.

## Weed Maintenance Workflow

The `weed-maintenance.yml` workflow updates WeedLocations region, district, and effective status.

### 🎯 Features

- **Scheduled Runs**: Daily at 00:15 NZT on production. The clock time stays fixed across daylight saving.
- **⚡ Manual Triggers**: On-demand execution with configurable options
- **🌍 Environment Selection**: Choose development or production environment
- **📊 Processing Modes**: Changed records (incremental) or full dataset processing
- **📈 Workflow Summary**: Real-time statistics showing updated and unassigned points
- **💾 Audit Table Storage**: Timestamps stored in ArcGIS audit table for reliable state management
- **⚡ Streamlined**: Simplified single-job execution with minimal overhead

### 🔧 Setup Instructions

#### 1. Configure GitHub Secrets

Add the following secrets to your repository (`Settings` → `Secrets and variables` → `Actions`):

**Development Environment:**
- `ARCGIS_USERNAME_DEV` - ArcGIS username for development
- `ARCGIS_PASSWORD_DEV` - ArcGIS password for development  
- `ARCGIS_PORTAL_URL_DEV` - ArcGIS portal URL for development

**Production Environment:**
- `ARCGIS_USERNAME_PROD` - ArcGIS username for production
- `ARCGIS_PASSWORD_PROD` - ArcGIS password for production
- `ARCGIS_PORTAL_URL_PROD` - ArcGIS portal URL for production

#### 2. Environment Configuration

Ensure your `weed_maintenance/config/environment_config.json` contains the required layer IDs for each environment. See the [weed maintenance configuration documentation](../weed_maintenance/README.md#configuration) for details. `EffectiveStatus` must exist on WeedLocations before the job writes.

### 🚀 Usage

#### Scheduled Execution
The workflow runs automatically daily at 00:15 NZT on the `production` environment using the `changed` mode (incremental processing). It does not update development.

#### Manual Execution
Go to `Actions` → `CAMS Weed Maintenance` → `Run workflow`

**Options:**
- **Environment**: Choose `development` or `production`
- **Processing Mode**:
  - `changed` - Records edited since the last run, plus visits that became due after that run
  - `all` - Every record, including historical overdue sites

Use environment `development` to update the development layer. The nightly schedule does not.

### 📊 Workflow Steps

1. **🏗️ Setup**: Checkout code, install Python, install dependencies
2. **🔧 Configure**: Set environment variables and credentials
3. **Process**: Run weed maintenance (handles timestamp management internally)
4. **📊 Summary**: Generate processing statistics

### 💾 State Storage

**Timestamp Storage** (permanent):
- **ArcGIS Audit Table**: Timestamps stored in "CAMS Process Audit" table
- **Per-Environment**: Separate records for development and production environments
- **Process-Specific**: Supports multiple CAMS utilities sharing the same audit table
- **Reliable**: Direct integration with ArcGIS platform eliminates external dependencies

### 🔍 Monitoring

#### Success Indicators
- ✅ All steps complete without errors
- ✅ Spatial assignments updated successfully
- ✅ Workflow summary generated with statistics
- ✅ Timestamp stored in ArcGIS audit table

#### Failure Scenarios
- ❌ Authentication failures (check secrets)
- ❌ Network issues (automatic retry built-in)
- ❌ Data validation errors (check source data)

### 🛠️ Troubleshooting

#### Common Issues

**"Environment not found in configuration"**
- Verify `weed_maintenance/config/environment_config.json` contains the specified environment
- Check that all required layer IDs are present

**"Authentication failed"**
- Verify GitHub secrets are correctly set
- Check that credentials have access to the specified portal and layers

**"No features to process"** 
- Normal for incremental runs when no changes occurred
- Use `mode: all` to force processing all records

**"Processing all records unexpectedly"**
- Check if audit table contains timestamp records for the environment
- Verify script can access the ArcGIS audit table (table ID: eb9b12249d794244ad82e54ad42dd58e)
- First run on an environment will process all records and create initial audit record

**Timestamp/State Issues**
- Timestamps are stored in the "CAMS Process Audit" ArcGIS table
- Each environment (dev/prod) maintains separate audit records
- ProcessName field identifies this utility ("weed_maintenance"). The first run copies the timestamp from "spatial_field_updater" for that environment.

#### Debugging Steps

1. **Review Logs**: Check detailed logs in the workflow run page
2. **Test Manually**: Use `workflow_dispatch` with environment `development` and mode `changed`
3. **Check Permissions**: Ensure service account has edit permissions on target layers
4. **Check Summary**: Review workflow summary for processing statistics

### 📈 Performance

Expected processing times:
- **5,000 records**: ~2-5 minutes
- **54,000 records**: ~10-15 minutes  
- **100,000+ records**: ~20-30 minutes

The workflow has a 30-minute timeout for streamlined execution.

### 🔒 Security

- **Credentials**: Stored securely in GitHub Secrets
- **Environment Separation**: Dev/prod credentials are completely separate
- **Principle of Least Privilege**: Each environment uses dedicated service accounts
- **Audit Trail**: All runs are logged with detailed workflow summaries

### 🏗️ Architecture

```mermaid
graph TD
    A[GitHub Actions Trigger] --> B{Event Type}
    B -->|Schedule| C[Production Environment]
    B -->|Manual| D[Selected Environment]
    
    C --> E[Single Spatial Update Job]
    D --> E
    
    E --> F[Spatial Processing]
    F --> G[Workflow Summary]
```

This simplified workflow provides reliable, automated spatial field updates with streamlined execution and comprehensive statistics.