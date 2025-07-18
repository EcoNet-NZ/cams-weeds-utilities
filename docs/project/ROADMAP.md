# CAMS Utilities Framework - Development Roadmap

## Overview

This roadmap delivers the CAMS Utilities modular framework through iterative, value-driven development. The framework provides shared infrastructure for multiple processing modules, with the Spatial Query Optimization system as the first implementation. Each increment provides testable functionality that builds toward a comprehensive automation platform for the Conservation Activity Management System.

---

## Phase 1: Core Framework Foundation (✅ COMPLETED)

### 1. CAMS Core Framework Setup ✅ COMPLETED

- **Outcome:** Modular project structure with shared core framework for all processing modules
- **Increment:**
  - ✅ Created modular project structure: src/ (core framework), modules/, config/, tests/
  - ✅ Implemented ConfigLoader utility with JSON configuration files
  - ✅ Created environment_config.json with dev/prod environment settings
  - ✅ Created field_mapping.json with standardized ArcGIS field definitions
  - ✅ Set up requirements.txt with core dependencies (arcgis>=2.4.1, tenacity>=8.0.0, func-timeout>=4.3.0)
  - ✅ Established custom exception hierarchy (CAMSBaseException and domain-specific exceptions)
- **Quality:** ✅ Unit tests implemented for configuration loading, code review completed
- **Feedback:** ✅ Configuration structure validated for multi-environment deployment

### 2. ArcGIS Connectivity Infrastructure ✅ COMPLETED

- **Outcome:** Production-ready ArcGIS connectivity shared across all modules
- **Increment:**
  - ✅ Implemented AuthHandler with environment variable-based authentication
  - ✅ Created ArcGISConnector with retry logic (tenacity), timeout handling (func-timeout)
  - ✅ Added EnvironmentValidator for cross-environment operation prevention
  - ✅ Implemented ConnectionTester for layer accessibility verification
  - ✅ Set up GitHub secrets structure for dev/prod environments
  - ✅ Added fail-fast validation on startup with credential verification
- **Quality:** ✅ 33 passing tests (16 AuthHandler + 17 ArcGISConnector), integration tests completed
- **Feedback:** ✅ Connection stability and authentication verified across environments

---

## Phase 2: Spatial Query Processor Module (Now)

### 3. Spatial Query Processor Module Structure

- **Outcome:** Complete module structure implementing ModuleProcessor interface for spatial optimization
- **Increment:**
  - Create modules/spatial_query_processor/ module directory structure
  - Implement spatial_query_processor/main.py as module entry point
  - Create spatial_config.json with spatial processing configuration
  - Implement SpatialProcessor class inheriting from ModuleProcessor interface
  - Create spatial_query_processor/models/ with WeedLocation and ProcessMetadata data models
  - Add spatial_query_processor/tests/ with module-specific test structure
  - Integrate module with shared core framework (config, connection, logging, exceptions)
- **Quality:** Unit tests for module structure, integration tests with core framework
- **Feedback:** Validate module interface compliance and core framework integration

### 4. Layer Access and Metadata Management

- **Outcome:** Reliable access to spatial layers with metadata retrieval for the spatial processor
- **Increment:**
  - Implement layer access operations using shared ArcGISConnector
  - Add layer metadata retrieval (Date updated, field schema validation) for WeedLocations, Region, District layers
  - Create ProcessMetadata model for tracking spatial processing status
  - Implement field mapping validation against actual layer schemas using shared field_mapping.json
  - Add layer ID verification for environment consistency using shared configuration
  - Create metadata table access for Weeds Area Metadata (dev/prod environment naming)
- **Quality:** Integration tests for layer access, unit tests for data models
- **Feedback:** Validate field mappings against production layer schemas

### 5. Change Detection System

- **Outcome:** Intelligent detection of changes requiring spatial reprocessing within the module
- **Increment:**
  - Implement SpatialChangeDetector extending framework change detection patterns
  - Add EditDate_1 field monitoring for modified weed locations
  - Create logic for full reprocessing vs incremental processing decisions
  - Implement metadata table reading for previous processing state using shared metadata patterns
  - Add change detection result models and reporting leveraging shared logging
- **Quality:** Unit tests for change detection logic, integration tests for metadata comparison
- **Feedback:** Validate change detection accuracy with sample data modifications

### 6. Spatial Query Processing Engine

- **Outcome:** Core spatial intersection processing between weed locations and area boundaries
- **Increment:**
  - Implement spatial intersection queries (weed geometry with region/district polygons)
  - Add batch processing logic for handling large datasets using framework patterns
  - Create assignment logic using REGC_code and TALB_code source fields from shared configuration
  - Implement spatial query optimization with appropriate filters
  - Add processing metrics and performance monitoring using shared logging infrastructure
- **Quality:** Unit tests for spatial logic, integration tests with sample geometries
- **Feedback:** Validate spatial accuracy with known test cases and performance benchmarks

### 7. Assignment Updates and Metadata Management

- **Outcome:** Reliable updates to WeedLocations with region/district codes and processing status tracking
- **Increment:**
  - Implement batch update operations for RegionCode and DistrictCode fields using shared ArcGIS connector
  - Add SpatialMetadataManager implementing framework metadata patterns
  - Create fail-safe metadata writing (only on successful completion) following framework standards
  - Implement update validation and error handling using shared exception hierarchy
  - Add processing metrics (records processed, duration, success rate) using shared logging
- **Quality:** Unit tests for update logic, integration tests for metadata management
- **Feedback:** Verify update accuracy and metadata reliability with test datasets

---

## Phase 3: Module Integration and Production Readiness (Next)

### 8. Dry-Run Mode and Module Validation

- **Outcome:** Safe testing capability for the spatial module without data modification
- **Increment:**
  - Implement --dry-run mode in spatial_query_processor/main.py following framework patterns
  - Add dry-run support across all spatial processing components
  - Create comprehensive logging of planned changes without execution using shared logging
  - Add validation reporting and processing metrics in dry-run mode
  - Create dry-run specific test coverage for the spatial module
- **Quality:** Unit tests for dry-run mode, integration tests with real data
- **Feedback:** Validate dry-run accuracy matches actual processing results

### 9. Spatial Module Orchestration and CLI

- **Outcome:** Complete spatial processing workflow with module interface compliance
- **Increment:**
  - Complete SpatialProcessor implementation with ModuleProcessor interface
  - Add complete workflow coordination between all spatial components
  - Create comprehensive error handling using shared exception hierarchy
  - Implement command-line interface in main.py with environment and dry-run options
  - Add processing summary reporting using shared logging infrastructure
- **Quality:** Unit tests for orchestration, end-to-end integration tests
- **Feedback:** Validate complete workflow with real development environment data

### 10. GitHub Actions for Spatial Processor

- **Outcome:** Automated daily spatial processing with multi-environment deployment
- **Increment:**
  - Create spatial-processor.yml GitHub Actions workflow with matrix strategy for dev/prod
  - Implement cron scheduling for 9:05pm NZT daily execution
  - Add environment-specific secret management using existing GitHub secrets
  - Create artifact collection for spatial processing logs
  - Add manual trigger capability for testing
- **Quality:** Test workflow in development environment, validate secret management
- **Feedback:** Verify scheduling reliability and environment isolation

---

## Phase 4: Spatial Module Enhancement and Monitoring (Later)

### 11. Spatial Module Performance Optimization

- **Outcome:** Optimized spatial processing performance with comprehensive monitoring
- **Increment:**
  - Implement spatial query optimization and geometry simplification
  - Add performance metrics collection specific to spatial processing
  - Create processing time analysis and bottleneck identification for large datasets
  - Implement adaptive batch sizing for spatial operations
  - Add long-term performance trend tracking using framework monitoring
- **Quality:** Performance tests with various data volumes, monitoring validation
- **Feedback:** Measure spatial processing time improvements and resource efficiency

### 12. Enhanced Error Handling and Recovery

- **Outcome:** Production-grade error handling for spatial processing with detailed troubleshooting
- **Increment:**
  - Enhance spatial module exception handling with domain-specific error categories
  - Add detailed error logging with spatial processing context
  - Implement spatial processing timeout handling and resource cleanup
  - Create spatial-specific error notification and alerting mechanisms
  - Add recovery procedures documentation for spatial processing failures
- **Quality:** Unit tests for spatial error scenarios, integration tests for failure modes
- **Feedback:** Validate error handling effectiveness with simulated spatial processing failures

### 13. Dashboard Integration and Status Display

- **Outcome:** CAMS dashboard displays spatial processing status and layer version information
- **Increment:**
  - Verify dashboard consumption of Weeds Area Metadata table
  - Create dashboard indicators for last spatial processing timestamp
  - Add spatial processing status visualization (Success/Error states)
  - Implement layer version display and mismatch detection
  - Create spatial processing history and trend widgets
- **Quality:** Integration tests with dashboard consumption, user acceptance testing
- **Feedback:** Validate dashboard usability and information clarity with end users

---

## Phase 5: Framework Expansion and Additional Modules (Later)

### 14. Data Sync Module Development

- **Outcome:** Second processing module demonstrating framework extensibility and reuse
- **Increment:**
  - Create modules/data_sync_module/ following established module patterns
  - Implement DataSyncProcessor inheriting from ModuleProcessor interface
  - Add data_sync_config.json with sync-specific configuration
  - Create bidirectional data synchronization logic between ArcGIS layers
  - Implement conflict resolution and audit trail functionality
  - Add data_sync.yml GitHub Actions workflow with hourly scheduling
- **Quality:** Unit tests for sync logic, integration tests with framework components
- **Feedback:** Validate framework reusability and module independence

### 15. Report Generator Module Development

- **Outcome:** Third processing module for automated report generation from CAMS data
- **Increment:**
  - Create modules/report_generator/ with template-based reporting system
  - Implement ReportProcessor for multi-format output (PDF, Excel, CSV)
  - Add report_config.json with template definitions and scheduling
  - Create report generation logic aggregating data from multiple sources
  - Implement email distribution and file storage capabilities
  - Add report-generator.yml GitHub Actions workflow with weekly scheduling
- **Quality:** Unit tests for report generation, integration tests for multi-format output
- **Feedback:** Validate report quality and distribution effectiveness

### 16. Framework Enhancement and Module Ecosystem

- **Outcome:** Enhanced framework supporting advanced module patterns and ecosystem growth
- **Increment:**
  - Implement plugin architecture for hot-swappable module loading
  - Add inter-module communication and coordination patterns
  - Create module dependency management and execution orchestration
  - Implement advanced caching and resource sharing across modules
  - Add configuration UI for module management and monitoring dashboard
  - Create module templates and development documentation
- **Quality:** Framework tests for advanced patterns, module ecosystem validation
- **Feedback:** Evaluate ease of new module development and framework extensibility

### 17. Production Scaling and Multi-Tenant Support

- **Outcome:** Production-ready framework supporting multiple CAMS instances and high-scale deployments
- **Increment:**
  - Implement cloud-native deployment patterns (Kubernetes, containers)
  - Add multi-tenant support for different CAMS organizations
  - Create API gateway for centralized module management and monitoring
  - Implement distributed caching and horizontal scaling patterns
  - Add advanced monitoring, alerting, and analytics across all modules
  - Create enterprise-grade security and compliance features
- **Quality:** Load testing, security validation, multi-tenant isolation verification
- **Feedback:** Validate production readiness and enterprise deployment patterns

---

## Iterative Development Notes

- **Living Document:** This roadmap will be updated based on feedback and changing requirements as the modular framework evolves
- **Feedback-Driven:** Each phase incorporates user feedback to inform subsequent module development and framework enhancements
- **Framework-First Approach:** Core framework foundation (Phase 1) enables rapid development of multiple processing modules
- **Module Independence:** Each module can be developed, tested, and deployed independently while leveraging shared infrastructure
- **Value Delivery:** Each increment delivers testable, valuable functionality with the spatial processor as the first complete implementation
- **Extensibility Focus:** Framework design prioritizes extensibility and reusability for future CAMS automation needs
- **Quality Focus:** Comprehensive testing of both framework components and individual modules ensures reliability across the ecosystem 