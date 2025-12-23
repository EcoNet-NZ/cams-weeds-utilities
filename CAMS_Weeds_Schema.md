# CAMS Weeds Schema Documentation

This document provides comprehensive field documentation for the CAMS (Conservation Activity Management System) Weeds schema, including field types, constraints, generation rules, and data flow.

**Last Updated**: 2025-12-23

---

## Table of Contents

1. [WeedLocations Layer](#weedlocations-layer)
2. [Visits_Table](#visits_table)
3. [Data Flow and Update Mechanisms](#data-flow-and-update-mechanisms)
4. [Field Naming Conventions](#field-naming-conventions)

---

## WeedLocations Layer

The WeedLocations layer (aka Weed Instance) is the primary feature layer for tracking individual weed infestations.

A new row is created for each new weed reported via the CAMS map or synchronised from iNaturalist.

Fields can be updated by a number of systems, see the Source column of the following table for details.

### System Fields

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| Weed Instance ID (OBJECTID) | `OBJECTID` | ObjectID | - | No | System | ArcGIS | Auto-increment, unique | Primary key, read-only |
| GlobalID | `GlobalID` | GlobalID | 38 | No | System | ArcGIS | UUID format | Unique identifier for relationships |
| (8.1) CreationDate | `CreationDate_1` | Date | - | Yes | System | ArcGIS | - | Timestamp when feature created |
| (8.1b) Creator | `Creator_1` | String | 255 | Yes | System | ArcGIS | - | Username of creator |
| (8.2) EditDate | `EditDate_1` | Date | - | Yes | System | ArcGIS | - | Timestamp of last edit |
| (8.2b) Editor | `Editor_1` | String | 255 | Yes | System | ArcGIS | - | Username of last editor |
| ZZZ ParentGUID OBSOLETE | `ParentGuid` | GUID | 38 | Yes | Deprecated | - | - | **OBSOLETE** - no longer used |
| (4.6) Date/Time Last Edited | `EditDate_SaveLast` | Date | - | Yes | System | ? | - | Alternate edit date field? |
| (4.7) Last Date/Time Edited, Version and UserID | `Editor_SaveLast` | String | 255 | Yes | System | ? | - | Combined edit metadata? |
| YYY Audit Trail #1 | `EditorNames_SaveLast` | String | 255 | Yes | System | ? | - | Historical editor names |
| (8.3) Audit Trail #0 | `Date_Editor_SaveLast` | String | 255 | Yes | System | ? | - | Combined date and editor info |
| Audit Trail #Creator | `UserName` | String | 255 | Yes | System | ? | - | Creator username |
| YYY Audit Trail #2 | `UserName2` | String | 255 | Yes | System | ? | - | Secondary audit trail |
| YYY-EditDateTime-TEST | `UserEditDateTime` | Date | - | Yes | System | ? | - | Test field for edit datetime |
| YYY-SaveContactDetails-Confidential | `SaveContactDetailsConfidential` | String | 255 | Yes | User | CAMS form? | - | Confidential contact saving flag |
| Image URLs | `ImageURLs` | String | - | Yes | User/System | iNat to CAMS | - | Semicolon-separated image URLs |
| Image Attribution | `ImageAttribution` | String | 255 | Yes | User/System | iNat to CAMS | - | Photo attribution text |
| Region Code | `RegionCode` | String | 50 | Yes | User | spatial_field_updater | - | Administrative region identifier |
| District Code | `DistrictCode` | String | 50 | Yes | User | spatial_field_updater | - | Administrative district identifier |
| last_user_edit | `last_user_edit` | String | 255 | Yes | System | ? | - | Last user to edit |
| last_user_edit_date | `last_user_edit_date` | Date | - | Yes | System | ? | - | Date of last user edit |

### Data Fields (Numbered in Order)

#### Section 1: Location and Basic Information

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (1.1) Weed Species (REQUIRED) | `SpeciesDropDown` | String | 255 | No | User | CAMS form, iNat to CAMS | Domain values | Required field, controlled vocabulary |
| (1.1b) "Other" or "Unidentified" weed details | `OtherWeedDetails` | String | 255 | Yes | User | CAMS form, iNat to CAMS | - | Free text for non-listed species |
| (1.2a) Weed Control Area Flag | `WeedsAreaFlag` | String | 50 | Yes | User | CAMS form | Yes/No | Indicates if part of control area |
| (1.2b) Name of Weed Control Area (auto-populated) | `NameOfControlArea` | String | 255 | Yes | System | ? | - | Auto-populated from spatial intersection |
| (1.3a) Location address / details (REQUIRED) | `LocationInfo` | String | 500 | No | User | CAMS form, iNat to CAMS, EasyEditor | - | Required location description |
| (1.3b) Property Name (if public - eg from signage) | `PropertyContactDetails` | String | 255 | Yes | User | CAMS form | - | Public property name |
| (1.3c) Link to confidential Property Contact details | `ContactURL` | String | 500 | Yes | User | CAMS form | URL format | Link to external contact info |
| (1.4) Social Media URL | `SocialMediaURL` | String | 500 | Yes | User | CAMS form | URL format | Social media reference |
| (1.5) Land Ownership Category | `LandOwnership` | String | 100 | Yes | User | CAMS form | Domain values | NZTA, Private, Council, Crown |
| (1.5b) GeoPrivacy | `GeoPrivacy` | String | 50 | Yes | User/System | CAMS form, iNat to CAMS | Domain values | Privacy level for location |
| (1.6) Date First Observed (if different from date added) | `DateDiscovered` | Date | - | Yes | User | CAMS form, iNat to CAMS | - | Initial discovery date |

#### Section 2: Status Information

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (2a) Current Status | `ParentStatusWithDomain` | String | 100 | Yes | System | Child-to-parent updater, Annual rollover, Daily rollover, CAMS form, iNat to CAMS, EasyEditor | Domain values | Synchronized from latest visit status; updated to PurpleHistoric by annual rollover |
| (2b) Number of pods, seed heads etc removed | `NbrPodsRemoved` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Count of reproductive structures |
| (2c) How Treated | `HowTreated` | String | 255 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | Treatment method description |
| (2cx) Treated? (Obsolete field) | `Treated` | String | 50 | Yes | Deprecated? | iNat to CAMS, EasyEditor | - | Whether treatment was applied partially or fully |
| (2d) Treatment substance | `TreatmentSubstance` | String | 255 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | Chemical used |
| (2e) Treatment details | `TreatmentDetails` | String | 500 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | Detailed treatment notes |
| (2f-1) Plants CONTROLLED - MATURE | `PlantsControlledMature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Count of mature plants controlled |
| (2f-2) Plants CONTROLLED - IMMATURE/JUVENILE | `PlantsControlledImmature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Count of immature plants controlled |
| (2f-3) Plants CONTROLLED - SEEDLINGS | `PlantsControlledSeedlings` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Count of seedlings controlled |
| (2h-1) MATURE plants REMAINING after this visit | `PlantsRemainingMature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Count of mature plants remaining |
| (2h-2) IMMATURE/JUVENILE plants REMAINING | `PlantsRemainingImmature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Count of immature plants remaining |
| (2h-3) SEEDLINGS REMAINING after this visit | `PlantsRemainingSeedings` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Count of seedlings remaining |
| (2j) Density at ground level | `DensityLevel01` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2k) Density at mid level | `DensityLevel02` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2l) Density at upper level | `DensityLevel03` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2m) Density at canopy level | `DensityLevel04` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2n) XXX Area Controlled | `AreaControlled` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Area in square meters |
| (2o) XXX Area Remaining | `AreaRemaining` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Area in square meters |

#### Section 3: Priority and Research

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (3.1) Priority For Action | `PriorityForAction` | String | 50 | Yes | User | CAMS form | Domain values | Prioritization flag |
| (3.2a) Research Flag | `ResearchFlag2` | String | 50 | Yes | User | CAMS form | Yes/No | Research interest indicator |
| (3.2b) Research Link | `ResearchLink` | String | 500 | Yes | User | CAMS form | URL format | Link to research information |
| (3.2c Xa) Who Visited/Took Action (auto entered) | `WhoVisitedName` | String | 255 | Yes | System | ? | - | Auto-populated from latest visit |
| (3.2c Xc) Member Name (as entered in Stamping Ground) | `TeamMemberNameFromVWA` | String | 255 | Yes | System | ? | - | From Stamping Ground app |
| (3.2c Xd) Team Name (as entered in Stamping Ground) | `TeamFromVWA` | String | 255 | Yes | System | ? | - | From Stamping Ground app |
| (3.2c Xdb) Team that Visited/Took Action (auto) | `TeamThatTookAction` | String | 255 | Yes | System | ? | - | Auto-populated team name |
| (3.2zzz) ZZZ Competition team code | `CompetitionTeamCode` | String | 100 | Yes | User | ? | - | For competition events |
| (3.5) Business Unit Owning This Record | `UnitOwnership` | String | 100 | Yes | User | CAMS form | - | See WARNING in notes |
| (3.xx) Estimated Hours Required Next Visit | `EstimateHoursNextVisit` | Double | - | Yes | User | CAMS form | >= 0 | Effort estimate |

#### Section 4: Seasonal Status and Rollover

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (4.1) Rollover Audit Log | `audit_log` | String | - | Yes | System | Annual rollover, Daily rollover | - | Tracks rollover history |
| (4.2) Spring 2021 Status | `LastSeasonStatus` | String | 100 | Yes | Historical | Annual rollover | Domain values | Historical status field |
| (4.3) Spring 2022 Status | `StatusAt202211` | String | 100 | Yes | Historical | Annual rollover | Domain values | Historical status field |
| (4.4) Spring 2023 Status | `StatusAt202310` | String | 100 | Yes | Historical | Annual rollover | Domain values | Historical status field |
| (4.5) Spring 2024 Status | `StatusAt202410` | String | 100 | Yes | Historical | Annual rollover | Domain values | Historical status field |
| (4.5a) Spring 2025 Status | `StatusAt202510` | String | 100 | Yes | System | Annual rollover | Domain values | Backup field for status before October 2025 rollover |
| XXX Status as at last Spring | `StatusLastSpring` | String | 100 | Yes | System | Annual rollover | Domain values | Status comparison field |
| XXX Status as at Spring before last | `StatusPreviousSpring` | String | 100 | Yes | System | Annual rollover | Domain values | Historical comparison |
| (4.8) Map Version ID | `SiteSource` | String | 100 | Yes | User/System | CAMS form, iNat to CAMS | - | Source map identifier |
| (4a) MonthsTillNextVisit | `MonthsTillNextVisit` | Integer | - | Yes | User | CAMS form | >= 0 | Months until next visit |
| (4aa) Date for next visit/action | `DateForReturnVisit` | Date | - | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | Scheduled return date |
| (4aXX) Weeks till next visit/action | `WeeksTillNextVisit` | Integer | - | Yes | Calculated | CAMS form | >= 0 | Calculated from months |
| (4b) Next steps | `NextSteps` | String | 500 | Yes | User | CAMS form | - | Action notes |
| (4c) Help needed | `HelpNeeded` | String | 500 | Yes | User | CAMS form | - | Assistance requests |
| (4d) Contractor help | `ContractorEngaged` | String | 255 | Yes | User | CAMS form | - | Contractor involvement |
| (4dd) Contractor help | `ContractorEngaged` | String | 255 | Yes | User | CAMS form | - | Duplicate field? |
| (4e) Project/job details | `ProjectOrJob` | String | 255 | Yes | User | CAMS form | - | Associated project |
| (4f) Service Request or Job number | `ReqForServiceDetails` | String | 255 | Yes | User | CAMS form | - | Council job reference |
| (4g) Visit/action communication link | `CommunicationURL` | String | 500 | Yes | User | CAMS form | URL format | Communication reference |
| (4h) Social Media Visit URL | `SocialMediaVisitURL` | String | 500 | Yes | User | CAMS form | URL format | Social media visit post |
| (4.zzz) ZZZ Basic Options Selector | `BasicOptionsFlag` | String | 50 | Yes | User | CAMS form | - | Simplified options flag |

#### Section 5: Visit Details (From Last Visit)

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (5.1) Estimated effort (From Last Visit) | `Urgency` | Integer | - | Yes | System | Child-to-parent updater, EasyEditor | 1-5 scale | Formerly "Difficulty" |
| (5.2) Date Visit Made (From Last Visit) | `DateVisitMadeFromLastVisit` | Date | - | Yes | System | Child-to-parent updater, EasyEditor | - | **KEY FIELD** - synced from visits |
| (5.3) Date For Next Visit (From Last Visit) | `DateForNextVisitFromLastVisit` | Date | - | Yes | System | Child-to-parent updater, EasyEditor | - | Synced from visits |
| (5.4) Latest Visit Step (From Last Visit) | `LatestVisitStage` | String | 100 | Yes | System | Child-to-parent updater | Domain values | Synced from visits |
| (5.5) Latest Area M2 (From Last Visit) | `LatestArea` | Double | - | Yes | System | Child-to-parent updater, EasyEditor | >= 0 | Synced from visits |
| (5.6) Date Of Last Create (From Last Visit) | `DateOfLastCreateFromLastVisit` | Date | - | Yes | System | Child-to-parent updater | - | Visit creation timestamp |
| (5.7) Date Of Last Edit (From Last Visit) | `DateOfLastEditFromLastVisit` | Date | - | Yes | System | Child-to-parent updater | - | Visit edit timestamp |
| (5.4b) YYY Oldest growth stage - READ ONLY | `Age` | String | 100 | Yes | System | ? | - | Oldest recorded growth stage |
| (5.5c) YYY Number of Stems (Estimate) - READ ONLY | `NumberOfStems` | Double | - | Yes | System | ? | >= 0 | Stem count estimate |
| (5a) iNaturalist reference | `iNatRef` | String | 255 | Yes | User/System | iNat to CAMS | - | iNaturalist observation ID |
| (5b) iNaturalist URL | `iNatURL` | String | 500 | Yes | User/System | iNat to CAMS | URL format | Full iNat observation URL |
| (5c) Observation quality (iNat) | `ObservationQuality` | String | 50 | Yes | System | iNat to CAMS | Domain values | Research/Needs ID/Casual |

#### Section 6: iNaturalist Integration

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (6.1) iNaturalist URL | `iNatURL` | String | 500 | Yes | User/System | iNat to CAMS | URL format | Full iNat observation URL |
| (6.2) Location Accuracy (iNaturalist) | `LocationAccuracy` | Integer | - | Yes | System | iNat to CAMS | >= 0 | Accuracy in meters |
| (6.3) iNaturalist Latitude | `iNatLatitude` | Double | - | Yes | System | iNat to CAMS | -90 to 90 | WGS84 latitude |
| (6.4) iNaturalist Longitude | `iNatLongitude` | Double | - | Yes | System | iNat to CAMS | -180 to 180 | WGS84 longitude |

#### Section 7: Audit and Tracking

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (7.4) YYY Visit/Action Type | `VisitType` | String | 100 | Yes | System | ? | Domain values | Type of last visit action |
| (7a) Visit action data source AUTO-POPULATED | `VisitDataSource` | String | 100 | Yes | System | ? | Domain values | Source of visit data |
| (7b was 9.2) Date_EditorID_SaveLast (CHILD) | `Visit_Date_Editor_SaveLast` | String | 255 | Yes | System | ? | - | Visit edit metadata |
| (7c was 9.5) EditDate_SaveLast (CHILD) | `EditDate_SaveLast` | Date | - | Yes | System | ? | - | Visit edit date |
| (8b was 9.3) Date_Editor_Audit#0 (CHILD) | `Date_Editor_SaveLast` | String | 255 | Yes | System | ? | - | Visit audit trail |
| (8b was 9.4) Date_Editor_Audit#1 (CHILD) | `Editor_SaveLast` | String | 255 | Yes | System | ? | - | Visit editor audit |
| (8c was 9.4) Date_Editor_Audit#1 (CHILD) | `Editor_SaveLast` | String | 255 | Yes | System | ? | - | Duplicate? Visit editor audit |
| (8.6) XXX-SendEmail | `SendEmail` | String | 50 | Yes | User | ? | - | Email notification flag |

#### Section 8: Notes and Miscellaneous

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| ZZZ Weed Instance Notes 1024 chars | `WeedInstanceNotes` | String | 1024 | Yes | User | CAMS form | - | General notes field |
| Elevation | `Elevation` | Double | - | Yes | System | ? | - | Elevation in meters |

---

## Visits_Table

The Visits_Table is a related table that stores individual visit records for each weed location. Multiple visits can be associated with a single WeedLocations feature via the `GUID_visits` relationship.

### System Fields

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| OBJECTID | `OBJECTID` | ObjectID | - | No | System | ArcGIS | Auto-increment, unique | Primary key, read-only |
| YYY-GUID - Visit to Weed Location Link | `GUID_visits` | GUID | 38 | No | System | ArcGIS | Must match WeedLocations.GlobalID | **RELATIONSHIP KEY** |
| GlobalID | `GlobalID` | GlobalID | 38 | No | System | ArcGIS | UUID format | Unique identifier |
| CreationDate | `CreationDate_1` | Date | - | Yes | System | ArcGIS | - | Timestamp when record created |
| Creator | `Creator_1` | String | 255 | Yes | System | ArcGIS | - | Username of creator |
| EditDate | `EditDate_1` | Date | - | Yes | System | ArcGIS | - | Timestamp of last edit |
| Editor | `Editor_1` | String | 255 | Yes | System | ArcGIS | - | Username of last editor |
| YYY-GUID_Preserve | `GUID_Preserve` | GUID | 38 | Yes | System | ? | - | Preserved GUID for data integrity |
| Recorded date | `RecordedDate` | Date | - | Yes | System | CAMS form, iNat to CAMS, EasyEditor | - | Date record was entered |
| Recorded by user id | `RecordedByUserId` | String | 255 | Yes | System | CAMS form, iNat to CAMS, EasyEditor | - | User ID who recorded |
| Recorded by user name | `RecordedByUserName` | String | 255 | Yes | System | CAMS form, iNat to CAMS, EasyEditor | - | Username who recorded |

### Data Fields (Numbered in Order)

#### Section 1: Visit Information

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (1.1) ZZZ Visit Mode | `VisitMode` | String | 50 | Yes | User | CAMS form | Domain values | Visit mode type |
| (1a) Date of Visit | `DateCheck` | Date | - | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | **KEY FIELD** - actual visit date, MANDATORY from v0.8 onwards. If blank, to be populated with `CreationDate_1` otherwise if `CreationDate_1` is after 2025-09-10, or left blank otherwise |
| (1a) Date of Visit - User Specified | `DateCheckUserSpecified` | Date | - | Yes | User | CAMS form | - | User can override auto date |
| (1b) Visit Status (REQUIRED) | `WeedVisitStatus` | String | 100 | No | User | CAMS form, iNat to CAMS, EasyEditor | Domain values | Required, controlled vocabulary |
| (1b.2) Visit Status Prompt | `VisitStatusPrompt` | String | 100 | Yes | User | CAMS form | Domain values | Status selection helper |
| (1c) Plants present MATURE observed BEFORE work | `PlantsPresentMature` | Integer | - | Yes | User | CAMS form | >= 0 | Pre-work count |
| (1d) Plants present IMMATURE observed BEFORE | `PlantsPresentImmature` | Integer | - | Yes | User | CAMS form | >= 0 | Pre-work count |
| (1e) Height in metres | `Height` | Double | - | Yes | User | CAMS form, iNat to CAMS, EasyEditor | >= 0 | Plant height |
| (1f) Area in metres reported | `Area` | Double | - | Yes | User | CAMS form, iNat to CAMS, EasyEditor | >= 0 | Infestation area in m² |
| (1g) Checked nearby radius (m) | `CheckedNearbyRadius` | Double | - | Yes | User | CAMS form, iNat to CAMS | >= 0 | Search radius |
| (1h) Flowering? Fruiting? (Phenology) | `Flowering` | String | 100 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | Domain values | Reproductive status |
| (1i) Site difficulty | `SiteDifficulty` | String | 100 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | Domain values | Access/terrain difficulty |
| (1ix) YYY Nbr of Pods Burst - READ ONLY | `PodsBurst` | Integer | - | Yes | User | CAMS form | >= 0 | Count of burst seed pods |
| (1j) Check for BioControl activity | `BioControlInd` | String | 50 | Yes | User | CAMS form | Yes/No | Biocontrol present? |
| (1k) Location on property (if not obvious from dot) | `LocationOnProperty` | String | 500 | Yes | User | CAMS form | - | Detailed location notes |
| (1l) Seeds dispersed (estimate) | `SeedsDispersed` | Integer | - | Yes | User | CAMS form | >= 0 | Estimated seed dispersal |
| (1m) Safety Issues | `Difficulty` | String | 255 | Yes | User | CAMS form | - | Safety concerns |
| (1n) Notes | `Notes` | String | - | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | General visit notes |
| (1o) Sex | `Sex` | String | 50 | Yes | User | CAMS form | Domain values | For dioecious species |

#### Section 2: Work Performed

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (2a) Visit action step | `VisitStage` | String | 100 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | Domain values | Action taken during visit |
| (2b) Number of pods, seed heads etc removed | `NbrPodsRemoved` | Integer | - | Yes | User | CAMS form, iNat to CAMS, EasyEditor | >= 0 | Reproductive structures removed |
| (2d) Treatment substance | `TreatmentSubstance` | String | 255 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | Chemical/method used |
| (2e) Treatment details | `TreatmentDetails` | String | 500 | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | Detailed treatment notes |
| (2f-1) Plants CONTROLLED - MATURE | `PlantsControlledMature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Mature plants controlled |
| (2f-2) Plants CONTROLLED - IMMATURE/JUVENILE | `PlantsControlledImmature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Immature plants controlled |
| (2f-3) Plants CONTROLLED - SEEDLINGS | `PlantsControlledSeedlings` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Seedlings controlled |
| (2h-1) MATURE plants REMAINING after visit | `PlantsRemainingMature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Mature plants remaining |
| (2h-2) IMMATURE/JUVENILE plants REMAINING | `PlantsRemainingImmature` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Immature plants remaining |
| (2h-3) SEEDLINGS REMAINING after this visit | `PlantsRemainingSeedings` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Seedlings remaining |
| (2j) Density at ground level | `DensityLevel01` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2k) Density at mid level | `DensityLevel02` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2l) Density at upper level | `DensityLevel03` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2m) Density at canopy level | `DensityLevel04` | Integer | - | Yes | User | CAMS form | 0-5 scale | Density rating |
| (2n) XXX Area Controlled | `AreaControlled` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Area controlled in m² |
| (2o) XXX Area Remaining | `AreaRemaining` | Integer | - | Yes | User | CAMS form, EasyEditor | >= 0 | Area remaining in m² |

#### Section 3: Team and Effort

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (3.2aXc) Member Name (as entered in Stamping Ground) | `TeamMemberNameFromVWA` | String | 40 | Yes | User | ? | Max 40 chars | Team member identifier |
| (3.2aXd) Team Name (as entered in Stamping Ground) | `TeamFromVWA` | String | 40 | Yes | User | ? | Max 40 chars | Team identifier |
| (3.2aXdb) Team that Visited/Took Action (auto) | `TeamThatTookAction` | String | 256 | Yes | System | CAMS form | Max 256 chars | Auto-populated team name |
| (3.2cXa) Who Visited/Took Action (auto entered) [99] | `WhoVisitedName` | String | 256 | Yes | System | CAMS form | Max 256 chars | Auto-populated visitor name |
| (3a) Estimated effort for this visit (1=easy...5=huge) | `DifficultyChild` | Integer | - | Yes | User | CAMS form, EasyEditor | 1-5 scale | Effort rating |
| (3b) Hours spent in total on this visit by all volunteers | `HoursSpent` | Double | - | Yes | User | CAMS form, EasyEditor | >= 0 | Total volunteer hours |
| (3c) Number of volunteers | `NumberOfVolunteers` | Integer | - | Yes | User | CAMS form | >= 0 | Volunteer count |
| (3.2zzz) ZZZ Competition team code | `CompetitionTeamCode` | String | 100 | Yes | User | CAMS form | - | For competition events |
| (3.xx) Estimated Hours Required Next Visit | `EstimateHoursNextVisit` | Double | - | Yes | User | CAMS form, EasyEditor | >= 0 | Future effort estimate |
| ZZZ (3.3) Urgency For Return Visit/Action | `UrgencyForReturnVisit` | Integer | - | Yes | Deprecated | - | - | **OBSOLETE**  |

#### Section 4: Follow-up Planning

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (4a) MonthsTillNextVisit | `MonthsTillNextVisit` | Integer | - | Yes | User | CAMS form | >= 0 | Months until next visit |
| (4aa) Date for next visit/action | `DateForReturnVisit` | Date | - | Yes | User | CAMS form, iNat to CAMS, EasyEditor | - | Scheduled return date |
| (4aXX) Weeks till next visit/action | `WeeksTillNextVisit` | Integer | - | Yes | Calculated | CAMS form | >= 0 | Calculated from months |
| (4b) Next steps | `NextSteps` | String | 500 | Yes | User | CAMS form | - | Planned actions |
| (4c) Help needed | `HelpNeeded` | String | 500 | Yes | User | CAMS form | - | Assistance requests |
| (4d) Contractor help | `ContractorEngaged` | String | 255 | Yes | User | CAMS form | - | Contractor involvement |
| (4dd) Contractor help | `ContractorEngaged` | String | 255 | Yes | User | CAMS form | - | Duplicate field? |
| (4e) Project/job details | `ProjectOrJob` | String | 255 | Yes | User | CAMS form | - | Associated project |
| (4f) Service Request or Job number | `ReqForServiceDetails` | String | 255 | Yes | User | CAMS form | - | Council job reference |
| (4g) Visit/action communication link | `CommunicationURL` | String | 500 | Yes | User | CAMS form | URL format | Communication reference |
| (4h) Social Media Visit URL | `SocialMediaVisitURL` | String | 500 | Yes | User | CAMS form | URL format | Social media post |
| ZZZ (4aXX) Month for next visit/action | `MonthForReturnVisit` | String | 50 | Yes | Deprecated | - | - | **OBSOLETE** - use MonthsTillNextVisit |
| ZZZ Estimate of time required next visit (person hours) (DEPRECATED) | `HoursNextVisitEstimate` | Double | - | Yes | Deprecated | - | - | **OBSOLETE** - use EstimateHoursNextVisit |

#### Section 5: iNaturalist Integration

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (5a) iNaturalist reference | `iNatRef` | String | 255 | Yes | User/System | iNat to CAMS | - | iNaturalist observation ID |
| (5b) iNaturalist URL | `iNaturalistURL` | String | 500 | Yes | User/System | iNat to CAMS | URL format | Full iNat observation URL |
| (5c) Observation quality (iNat) | `ObservationQuality` | String | 50 | Yes | System | iNat to CAMS | Domain values | Research/Needs ID/Casual |

#### Section 6: Additional Fields

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (6a) Who Visited/Actioned - Email Address (DROP THIS FIELD - IMPLEMENT DIFFERENTLY? BUT NEED TO DISPLAY EXISTING DATA?) | `WhoVisitedEmail` | String | 255 | Yes | User | CAMS form | Email format | **DEPRECATED** - privacy concerns |

#### Section 7: Audit and Tracking

| Display Name | Field Name | Type | Length | Nullable | Generation | Source | Constraints | Notes |
|-------------|------------|------|--------|----------|------------|--------|-------------|--------|
| (7a) Visit action data source AUTO-POPULATED | `VisitDataSource` | String | 100 | Yes | System | CAMS form, EasyEditor | Domain values | Source of visit data (CAMS/iNat/etc) |
| (7b was 9.2) Date_EditorID_SaveLast (CHILD) | `Visit_Date_Editor_SaveLast` | String | 255 | Yes | System | ? | - | Visit edit metadata |
| (7c was 9.5) EditDate_SaveLast (CHILD) | `EditDate_SaveLast` | Date | - | Yes | System | ? | - | Visit last edit date |
| (8b was 9.3) Date_Editor_Audit#0 (CHILD) | `Date_Editor_SaveLast` | String | 255 | Yes | System | ? | - | Audit trail #0 |
| (8c was 9.4) Date_Editor_Audit#1 (CHILD) | `Editor_SaveLast` | String | 255 | Yes | System | ? | - | Audit trail #1 |
| (8.6) XXX-SendEmail | `SendEmail` | String | 50 | Yes | User | ? | - | Email notification flag |
| XXX 9.9 Test new integer | `XXXTestNewInteger` | Integer | - | Yes | Test | ? | - | **TEST FIELD** |

---

### CAMS Weeds Schema Rules

Assuming the child-parent updater and iNat synchroniser have run for the latest updates, the following fields in `WeedLocations` should be equivalent to field the latest row of the `Visits_Table` (ie the `Visits_Table` row with latest `DateCheck` datetime where `Visits_Table.GUID_Visits` = `WeedLocations.GlobalID`.

| WeedLocations field | Visits_Table field |
| `Urgency` | `DifficultyChild` |
| `ParentStatusWithDomain` | `WeedVisitStatus` | 
| `DateVisitMadeFromLastVisit` | `DateCheck` | 
| `DateForNextVisitFromLastVisit` | `DateForReturnVisit` | 
| `LatestVisitStage` | `VisitStage` | 
| `LatestArea` | `Area` | 
| `DateOfLastCreateFromLastVisit` | `CreationDate_1` | 
| `DateOfLastEditFromLastVisit` | `EditDate_1` | 

Exceptions:

1. These values will not be replicated where there are no matching `Visits_Table` rows.


| (5.1) Estimated effort (From Last Visit) | `Urgency` | Integer | - | Yes | System | Child-to-parent updater, EasyEditor | 1-5 scale | Formerly "Difficulty" |
| (5.2) Date Visit Made (From Last Visit) | `DateVisitMadeFromLastVisit` | Date | - | Yes | System | Child-to-parent updater, EasyEditor | - | **KEY FIELD** - synced from visits |
| (5.3) Date For Next Visit (From Last Visit) | `DateForNextVisitFromLastVisit` | Date | - | Yes | System | Child-to-parent updater, EasyEditor | - | Synced from visits |
| (5.4) Latest Visit Step (From Last Visit) | `LatestVisitStage` | String | 100 | Yes | System | Child-to-parent updater | Domain values | Synced from visits |
| (5.5) Latest Area M2 (From Last Visit) | `LatestArea` | Double | - | Yes | System | Child-to-parent updater, EasyEditor | >= 0 | Synced from visits |
| (5.6) Date Of Last Create (From Last Visit) | `DateOfLastCreateFromLastVisit` | Date | - | Yes | System | Child-to-parent updater | - | Visit creation timestamp |
| (5.7) Date Of Last Edit (From Last Visit) | `DateOfLastEditFromLastVisit` | Date | - | Yes | System | Child-to-parent updater | - | Visit edit timestamp |

---

## Data Flow and Update Mechanisms

### 1. CAMS Form Entry

The primary data entry method for field users. Creates new WeedLocations features and Visits_Table records.

**Creates:**
- New WeedLocations features with spatial location
- Related Visits_Table records linked via `GUID_visits`

**Sets:**
- User-entered fields (species, location, observations)
- System fields (creator, creation date)
- Initial values for parent fields

### 2. CAMS EasyEditor

Web-based editing interface that simplifies data entry of new visits. Prior to CAMS Weeds v0.8 it could only update CAMS weeds synced from iNaturalist. From v0.8 onwards it can also update CAMS weeds not synced from iNaturalist.

**Adds:**
- Visits_Table records

**Updates:**
- WeedLocations attributes

### 3. iNaturalist to CAMS Synchronizer

Automated process that syncs iNaturalist observations to CAMS.

**Frequency:** Runs on hourly schedule

### 4. Child-to-Parent Updater

Critical synchronization process that propagates latest visit data to parent WeedLocations features. This is a Power Automate process triggered by an ArcGIS WebHook.

**Field Mapping Table:**

| WeedLocations Field (Destination) | Visits_Table Field (Source) | Notes |
|----------------------------------|----------------------------|--------|
| `GlobalID` | `GUID_visits` | Relationship key |
| `Urgency` | `DifficultyChild` | Effort estimate (1-5 scale) |
| `ParentStatusWithDomain` | `WeedVisitStatus` | Current status |
| `DateVisitMadeFromLastVisit` | `DateCheck` | **KEY FIELD** - visit date |
| `DateForNextVisitFromLastVisit` | `DateForReturnVisit` | Scheduled return date |
| `LatestVisitStage` | `VisitStage` | Visit action step |
| `LatestArea` | `Area` | Infestation area (m²) |
| `DateOfLastCreateFromLastVisit` | `CreationDate_1` | Visit creation timestamp |
| `DateOfLastEditFromLastVisit` | `EditDate_1` | Visit edit timestamp |

**Logic:**
- Identifies "latest" visit by most recent `DateCheck` (or `CreationDate_1` if DateCheck is null)
- One-way update from child to parent
- Essential for keeping parent records current

**Frequency:** This is typically triggered within a few minutes of a new or updated Visits Table record.

### 5. Annual Rollover

Automated process that updates qualifying weed locations for annual re-checking. Runs annually on October 1st with production safeguards preventing early execution.

**Target Records:**
- 10 climbing/spreading species (MothPlant, OldMansBeard, CathedralBells, BananaPassionfruit, BluePassionFlower, Jasmine, JapaneseHoneysuckle, BlueMorningGlory, WoollyNightshade, Elaeagnus)
- Yellow/Orange/Green/Pink statuses
- Next visit due (≤ October 1st or null)
- Time criteria: 2 months for Yellow/Orange, 2 years for Green/Pink

**Updates WeedLocations:**
- `ParentStatusWithDomain` → 'PurpleHistoric' for eligible records
- `StatusAt202510` → Backs up all current status values before rollover
- `audit_log` → Appends rollover entry with date and previous status

**Last Visit Resolution:** Uses coalesce of `DateVisitMadeFromLastVisit`, `DateOfLastCreateFromLastVisit`, `DateDiscovered`

**Implementation:** `/annual_rollover/annual_rollover.py` with dry-run mode, retry logic, and Excel exports

### 6. Spatial Field Updater

High-performance automated process that pre-calculates region and district assignments to eliminate real-time spatial queries during dashboard filtering. Designed for daily processing of 54,000+ records in 10-15 minutes using GeoPandas bulk operations.

**Updates WeedLocations:**
- `RegionCode` ← 2-character region code (e.g., "02" for Auckland)
- `DistrictCode` ← 5-character district code (e.g., "04101" for Far North)

**Assignment Logic:**
- Primary: Exact spatial intersection with boundary polygons
- Fallback: Nearest boundary within 2km for edge cases (99.98% success rate)
- All layers use EPSG:2193 (NZTM) with geometry validation

**Processing Modes:**
- Incremental (default): Only records where `EditDate_1` > last run
- Full (`--mode all`): Reprocess entire dataset
- Change detection tracked in CAMS Process Audit table

**Implementation:** `/spatial_field_updater/spatial_field_updater.py` with retry logic and smart field comparison

---

## Field Naming Conventions

### Prefixes

- **YYY**: Experimental or in-development fields
- **XXX**: Deprecated or to-be-removed fields
- **ZZZ**: Obsolete fields (retained for historical data)

### Suffixes

- **`_1`**: System-generated variants (e.g., `CreationDate_1`, `Creator_1`)
- **`FromLastVisit`**: Parent fields synced from child visits
- **`FromVWA`**: Fields populated from Stamping Ground app (VWA = Volunteer Weed Area (aka StampingGround))

### Numbering System

Fields are numbered with a system like `(1.1)`, `(2a)`, `(3.2cXa)` which indicates:
- **First digit**: Major section/category
- **Letter/number combinations**: Subsections and related fields
- **X**: Indicates experimental or variant field

---

## Data Quality Considerations

### Critical Synchronization Field

**`DateVisitMadeFromLastVisit`** is the most critical field for data integrity:
- Should always match the latest visit's `DateCheck`
- Discrepancies indicate synchronization failures
- See `weed_visits_analyzer.py` tool for monitoring

### Required Fields

**WeedLocations:**
- `SpeciesDropDown` - Species identification required
- `LocationInfo` - Location description required

**Visits_Table:**
- `GUID_visits` - Relationship to parent required
- `WeedVisitStatus` - Visit status required

---

## Related Tools

- **`weed_visits_analyzer.py`**: Monitors synchronization between WeedLocations and Visits_Table, identifying discrepancies in the child-to-parent update process
- **`spatial_field_updater.py`**: Automated process that updates RegionCode and DistrictCode fields using high-performance GeoPandas spatial operations
- **`annual_rollover.py`**: Year-end process that updates qualifying weed instances to PurpleHistoric status for annual re-checking, with comprehensive backup and audit trail

---

*This documentation reflects the CAMS schema as at date of publication. Field definitions and behaviors may evolve with system updates.*
