1. Purpose
Automate the annual rollover of weed instance records, updating their status based on business rules, and generate a detailed log for each run.

2. Inputs
ArcGIS Feature Layer Endpoint: URL for querying and updating weed instance records.

3. Process Steps
3.1. Initialization
Set variables:
HTMLLog (string, for results table)
NewStatus (string, per record)
3.2. Fetch Records
Query the ArcGIS Feature Layer for records where:
SpeciesDropDown is one of:
MothPlant
OldMansBeard
CathedralBells
BananaPassionfruit
BluePassionFlower
Jasmine
JapaneseHoneysuckle
BlueMorningGlory
WoollyNightshade
Elaeagnus

ParentStatusWithDomain is one of:
YellowKilledThisYear
GreenNoRegrowthThisYear
OrangeDeadHeaded
PinkOccupantWillKillGrowth

3.3. Process Each Record
For each record:
Extract:
OBJECTID
SpeciesDropDown
ParentStatusWithDomain
Visit date fields: DateVisitMadeFromLastVisit, DateOfLastCreateFromLastVisit, DateDiscovered, DateForNextVisitFromLastVisit
Determine New Status:
If DateForNextVisitFromLastVisit is in the future: do nothing
Else if last visit date is within 2 months: do nothing
Else, based on ParentStatusWithDomain:
If "GreenNoRegrowthThisYear" and last visit within 2 years: do nothing, else PurpleHistoric
If "YellowKilledThisYear" or "OrangeDeadHeaded": PurpleHistoric
If "PinkOccupantWillKillGrowth" and last visit within 2 years: do nothing, else PurpleHistoric
Otherwise: do nothing
If species is not in the list: do nothing
Update ArcGIS Record (if status changes) and log this:
If NewStatus == "PurpleHistoric", update the following fields:
GlobalID: Used to identify the record.
ParentStatusWithDomain: Set to "PurpleHistoric".
audit_log: Append a new entry with the current UTC date, previous status, and a note indicating the annual rollover.
Format Example:
2024-06-13 Annual rollover from [PreviousStatus] to Purple; [Previous audit_log content]

7. Configurability
Allow configuration of ArcGIS endpoint, username, password as per the other scripts
