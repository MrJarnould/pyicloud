# PyiCloud Pydantic Models Analysis

**Created:** 2025-01-08
**Purpose:** Comprehensive analysis of all Pydantic models needed for PyiCloud refactoring
**Branch:** `pydantic-typer-refactor`

## Executive Summary

This document provides a detailed analysis of all Pydantic models needed to modernize the PyiCloud library. The analysis is based on a thorough examination of each file in the `pyicloud/` package, identifying data structures that would benefit from type safety, validation, and modern Python patterns.

## Analysis Methodology

1. **File-by-file examination** of the entire `pyicloud/` package
2. **Service-by-service analysis** of all iCloud services
3. **Data structure identification** from API responses, configurations, and internal state
4. **Priority classification** based on usage frequency and user impact
5. **Backward compatibility assessment** for each proposed model

## Current Architecture Overview

### Core Files Analyzed
- `base.py` (867 lines) - Authentication, core service management
- `session.py` (351 lines) - Session handling, cookie management
- `exceptions.py` (75 lines) - Exception hierarchy
- `cmdline.py` (454 lines) - CLI interface (target for Typer refactoring)

### Service Files Analyzed
- `services/findmyiphone.py` (261 lines) - Device location and management
- `services/photos.py` (1,225 lines) - Photo library, albums, assets
- `services/drive.py` (542 lines) - iCloud Drive file management
- `services/contacts.py` (127 lines) - Contact management
- `services/calendar.py` (430 lines) - Calendar and event management
- `services/account.py` (374 lines) - Account info, family, storage
- `services/reminders.py` (132 lines) - Reminders and task management
- `services/ubiquity.py` (129 lines) - Ubiquity/iCloud document sync
- `services/hidemyemail.py` (213 lines) - Hide My Email service
- `services/base.py` (33 lines) - Base service functionality

## Priority Classification

### **Priority 1: Core Authentication & Session Models**
*Critical for security and reliability*

### **Priority 2: Device Management Models**
*High user impact - device location/control*

### **Priority 3: Service Response Models**
*API response validation and type safety*

### **Priority 4: CLI Configuration Models**
*Typer migration and user experience*

### **Priority 5: Advanced Service Models**
*Enhanced features and future expansion*

---

## Model Selection Guidelines

**Use Pydantic When:**
- ✅ Data crosses boundaries (API, file, CLI)
- ✅ Complex validation rules needed
- ✅ JSON serialization required
- ✅ Data comes from untrusted sources
- ✅ Need rich error messages

**Use Dataclass When:**
- ✅ Internal-only data structures
- ✅ Simple type validation sufficient
- ✅ No JSON serialization needed
- ✅ Performance is critical
- ✅ Want minimal dependencies

---

## PRIORITY 1: Core Authentication & Session Models

### 1.1 Authentication Models

#### **SrpAuthenticationData → SrpPassword (Dataclass Refactor)**
**Source:** `base.py:SrpPassword` class
**Problem:** Incomplete initialization, AttributeError risks, no validation
**Solution:** Dataclass with validation - matches existing usage pattern
```python
from dataclasses import dataclass
from typing import Optional
import hashlib

@dataclass
class SrpPassword:
    """SRP password with type safety and validation."""
    password: str
    salt: Optional[bytes] = None
    iterations: Optional[int] = None
    key_length: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate password after initialization."""
        if not self.password or not self.password.strip():
            raise PyiCloudPasswordException("Password cannot be empty")

    def set_encrypt_info(self, salt: bytes, iterations: int, key_length: int) -> None:
        """Set encryption parameters with validation."""
        if not salt:
            raise ValueError("Salt cannot be empty")
        if iterations <= 0:
            raise ValueError("Iterations must be positive")
        if key_length <= 0:
            raise ValueError("Key length must be positive")

        self.salt = salt
        self.iterations = iterations
        self.key_length = key_length

    def encode(self) -> bytes:
        """Encode password using PBKDF2-HMAC-SHA256."""
        if not all([self.salt, self.iterations, self.key_length]):
            raise RuntimeError("Must call set_encrypt_info() first")

        password_hash = hashlib.sha256(self.password.encode("utf-8")).digest()
        return hashlib.pbkdf2_hmac(
            "sha256",
            password_hash,
            self.salt,
            self.iterations,
            self.key_length,
        )
```

**Why Dataclass over Pydantic:**
- ✅ **Perfect Pattern Match**: Supports existing two-phase initialization
- ✅ **Zero Dependencies**: Uses standard library only
- ✅ **Drop-in Replacement**: Minimal migration effort
- ✅ **Type Safety**: Automatic type hints and IDE support
- ✅ **Validation**: Custom validation in `__post_init__`
- ❌ **Pydantic Overkill**: Too heavy for simple data holder use case

#### **AuthenticationContext**
**Source:** `base.py:PyiCloudService.__init__` and authentication methods
**Purpose:** Internal authentication state management
```python
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class AuthenticationContext:
    """Internal authentication state - no external serialization needed."""
    apple_id: str
    client_id: str
    is_china_mainland: bool = False
    with_family: bool = True
    requires_2fa: bool = False
    requires_2sa: bool = False
    is_trusted_session: bool = False
    session_endpoints: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate authentication context."""
        if not self.apple_id or "@" not in self.apple_id:
            raise ValueError("Valid Apple ID email required")
        if not self.client_id:
            raise ValueError("Client ID required")
```

**Why Dataclass over Pydantic:**
- ✅ **Internal State**: Used only within PyiCloudService
- ✅ **Simple Validation**: Basic type checking sufficient
- ✅ **Performance**: Created frequently during auth flows
- ✅ **No Serialization**: Never serialized to JSON/files

#### **TrustedDevice**
**Source:** `base.py:trusted_devices` property and 2FA handling
**Purpose:** 2FA trusted device information from Apple API
```python
class TrustedDevice(BaseModel):
    device_type: str = Field(..., description="Device type (e.g., 'SMS', 'PHONE')")
    areacode: Optional[str] = Field(None, description="Phone area code")
    phonenumber: Optional[str] = Field(None, description="Masked phone number")
    device_id: str = Field(..., description="Device identifier")
    trusted_device_id: str = Field(..., description="Trusted device ID")
```

**Why Pydantic (Correctly):**
- ✅ **External API Data**: Comes from Apple's 2FA endpoints
- ✅ **JSON Parsing**: Parsed from Apple API responses

### 1.2 Session Management Models

#### **SessionData**
**Source:** `session.py:PyiCloudSession._data` and session persistence
**Purpose:** Session state with file persistence
```python
class SessionData(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    session_id: Optional[str] = Field(None, description="Apple session ID")
    session_token: Optional[str] = Field(None, description="Session token")
    scnt: Optional[str] = Field(None, description="Session count token")
    trust_token: Optional[str] = Field(None, description="Trust token")
    account_country: Optional[str] = Field(None, description="Account country code")

    model_config = ConfigDict(
        # Exclude sensitive fields from logs/serialization
        json_schema_extra={
            "sensitive_fields": ["session_token", "trust_token", "scnt"]
        }
    )
```

**Why Pydantic (Correctly):**
- ✅ **File Persistence**: Serialized to/from JSON files
- ✅ **External Data**: Contains tokens from Apple API
- ✅ **Security Features**: Needs sensitive field redaction

#### **CookieJarConfig**
**Source:** `session.py:PyiCloudCookieJar` and cookie handling
**Purpose:** Simple internal configuration for cookie handling
```python
from dataclasses import dataclass

@dataclass
class CookieJarConfig:
    """Internal cookie configuration - no external serialization needed."""
    cookie_directory: str
    session_file_path: str
    auto_save: bool = True
    ignore_discard: bool = True
    ignore_expires: bool = True

    def __post_init__(self) -> None:
        """Validate paths exist or can be created."""
        import os
        if not os.path.exists(os.path.dirname(self.cookie_directory)):
            raise ValueError(f"Cookie directory parent must exist: {self.cookie_directory}")
```

**Why Dataclass over Pydantic:**
- ✅ **Internal Configuration**: Used only within PyiCloudSession
- ✅ **Simple Validation**: Basic path checking sufficient
- ✅ **No Serialization**: Configuration set programmatically, not from files
- ✅ **Performance**: Created during session initialization

### 1.3 Service Configuration Models

#### **ServiceEndpoints**
**Source:** `base.py:_setup_endpoints` and webservices data
**Purpose:** Dynamic service endpoint management from Apple API
```python
class ServiceEndpoints(BaseModel):
    auth_endpoint: str = Field(..., description="Authentication endpoint")
    home_endpoint: str = Field(..., description="Home page endpoint")
    setup_endpoint: str = Field(..., description="Setup service endpoint")
    webservices: Dict[str, WebServiceInfo] = Field(default_factory=dict, description="Available services")

class WebServiceInfo(BaseModel):
    url: str = Field(..., description="Service URL")
    status: Optional[str] = Field(None, description="Service status")
    pcs_required: Optional[bool] = Field(None, description="PCS consent required")
    upload_url: Optional[str] = Field(None, description="Upload URL for media services")
```

**Why Pydantic (Correctly):**
- ✅ **External API Data**: Comes from Apple's webservices endpoint
- ✅ **JSON Parsing**: Parsed from Apple API responses
- ✅ **Complex Structure**: Nested models with validation

---

## PRIORITY 2: Device Management Models

### 2.1 Core Device Models

#### **DeviceFeatures**
**Source:** `services/findmyiphone.py:AppleDevice` device capabilities
**Purpose:** Device capability flags - optimized for frequent access
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DeviceFeatures:
    """Device capability flags - optimized for internal use."""
    # Location and tracking
    LOC: Optional[bool] = None  # Location services
    LCK: Optional[bool] = None  # Remote lock
    LMG: Optional[bool] = None  # Lost mode
    MSG: Optional[bool] = None  # Message display
    SND: Optional[bool] = None  # Sound alerts
    WIP: Optional[bool] = None  # Remote wipe

    # Advanced features
    ALS: Optional[bool] = None  # Alarm sound
    CLT: Optional[bool] = None  # Clear text
    PRM: Optional[bool] = None  # Persistent ring
    SVP: Optional[bool] = None  # Supervised mode
    # ... (30+ more feature flags from real API)

    def has_location_services(self) -> bool:
        """Check if device supports location services."""
        return self.LOC is True

    def has_remote_actions(self) -> bool:
        """Check if device supports remote actions."""
        return any([self.LCK, self.WIP, self.SND, self.MSG])
```

**Why Dataclass over Pydantic:**
- ✅ **High Frequency**: Accessed frequently during device operations
- ✅ **Simple Data**: Just optional boolean flags
- ✅ **Performance Critical**: Part of device location/action paths
- ✅ **Internal Use**: Used heavily in internal device logic

**Note**: For API parsing, create a Pydantic adapter:
```python
class DeviceFeaturesModel(BaseModel):
    """Pydantic adapter for API parsing."""
    # ... same fields as dataclass

    def to_dataclass(self) -> DeviceFeatures:
        """Convert to performance-optimized dataclass."""
        return DeviceFeatures(**self.model_dump())
```

#### **AppleDeviceInfo**
**Source:** `services/findmyiphone.py:AppleDevice` class and device data
**Purpose:** Complete device information from Apple API
```python
class BatteryStatus(str, Enum):
    UNKNOWN = "Unknown"
    CHARGING = "Charging"
    NOT_CHARGING = "NotCharging"
    CHARGED = "Charged"

class DeviceStatus(str, Enum):
    ONLINE = "200"
    OFFLINE = "201"
    PENDING = "203"
    UNREGISTERED = "204"

class AppleDeviceInfo(BaseModel):
    id: str = Field(..., description="Device unique identifier")
    name: str = Field(..., description="User-assigned device name")
    device_class: str = Field(..., description="Device type (iPhone, iPad, etc.)")
    device_model: str = Field(..., description="Device model identifier")
    device_display_name: str = Field(..., description="Human-readable device name")
    model_display_name: str = Field(..., description="Model display name")

    # Status and battery
    device_status: DeviceStatus = Field(..., description="Current device status")
    battery_level: Optional[float] = Field(None, ge=0, le=1, description="Battery level (0-1)")
    battery_status: Optional[BatteryStatus] = Field(None, description="Battery charging status")
    low_power_mode: bool = Field(default=False, description="Low power mode enabled")

    # Device capabilities
    features: DeviceFeatures = Field(default_factory=DeviceFeatures, description="Device feature flags")
    is_mac: bool = Field(default=False, description="Is Mac device")
    location_capable: bool = Field(default=True, description="Supports location services")
    location_enabled: bool = Field(default=True, description="Location services enabled")

    # Tracking and security
    this_device: bool = Field(default=False, description="Is current device")
    activation_locked: bool = Field(default=False, description="Activation lock enabled")
    passcode_length: int = Field(default=0, description="Passcode length")

    model_config = ConfigDict(str_strip_whitespace=True)
```

**Why Pydantic (Correctly):**
- ✅ **External API Data**: Comes from Apple Find My iPhone API
- ✅ **Complex Validation**: Multiple enums, ranges, business rules
- ✅ **JSON Parsing**: Parsed from Apple API responses

#### **DeviceLocation**
**Source:** `services/findmyiphone.py:AppleDevice.location` property
**Purpose:** Device location data with validation
```python
class PositionType(str, Enum):
    UNKNOWN = "Unknown"
    WIFI = "Wifi"
    CELL = "Cell"
    GPS = "GPS"

class DeviceLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    altitude: float = Field(..., description="Altitude in meters")
    horizontal_accuracy: float = Field(..., ge=0, description="Horizontal accuracy in meters")
    vertical_accuracy: float = Field(..., description="Vertical accuracy in meters")

    position_type: PositionType = Field(..., description="Location source type")
    location_mode: Optional[str] = Field(None, description="Location mode")
    time_stamp: int = Field(..., description="Location timestamp")
    is_old: bool = Field(default=False, description="Location data is stale")
    is_inaccurate: bool = Field(default=False, description="Location may be inaccurate")
    location_finished: bool = Field(default=True, description="Location update complete")

    @field_validator('time_stamp')
    @classmethod
    def validate_timestamp(cls, v):
        if v < 0:
            raise ValueError('Timestamp must be positive')
        return v
```

### 2.2 Device Action Models

#### **DeviceActionRequest**
**Source:** `services/findmyiphone.py` device action methods
**Purpose:** Internal request structures for device actions
```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PlaySoundRequest:
    """Internal request for playing sound on device."""
    device_id: str
    subject: str = "Find My iPhone Alert"
    client_context: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.client_context is None:
            self.client_context = {"fmly": True}
        if not self.device_id:
            raise ValueError("Device ID required")

@dataclass
class DisplayMessageRequest:
    """Internal request for displaying message on device."""
    device_id: str
    text: str
    subject: str = "Find My iPhone Alert"
    sound: bool = False
    user_text: bool = True

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("Device ID required")
        if not self.text or not self.text.strip():
            raise ValueError("Message text required")

@dataclass
class LostModeRequest:
    """Internal request for enabling lost mode on device."""
    device_id: str
    phone_number: str
    message: str = "This device has been lost. Please call me."
    passcode: str = ""
    email_updates: bool = True
    user_text: bool = True
    sound: bool = True

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("Device ID required")
        if not self.phone_number:
            raise ValueError("Contact phone number required")
        # Basic phone validation
        clean_number = self.phone_number.replace('+', '').replace('-', '').replace(' ', '')
        if not clean_number.isdigit():
            raise ValueError("Invalid phone number format")
```

**Why Dataclass over Pydantic:**
- ✅ **Internal Only**: Used within device action methods
- ✅ **Simple Validation**: Basic field validation sufficient
- ✅ **No Serialization**: Never sent as JSON (converted to Apple's format)
- ✅ **Performance**: Created for each device action

---

## PRIORITY 3: Service Response Models

### 3.1 Photos Service Models

#### **PhotoAsset**
**Source:** `services/photos.py:PhotoAsset` class
**Purpose:** Individual photo/video metadata from Apple Photos API
```python
class PhotoItemType(str, Enum):
    IMAGE = "image"
    MOVIE = "movie"

class PhotoAsset(BaseModel):
    record_name: str = Field(..., description="Unique photo record identifier")
    filename: str = Field(..., description="Original filename")

    # Metadata
    created: datetime = Field(..., description="Photo creation date")
    asset_date: datetime = Field(..., description="Asset date")
    added_date: datetime = Field(..., description="Date added to library")

    # Media properties
    item_type: PhotoItemType = Field(..., description="Media type")
    size: int = Field(..., ge=0, description="File size in bytes")
    dimensions: Tuple[int, int] = Field(..., description="Width x Height dimensions")

    # Versions available
    versions: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Available photo versions")

    # Master and asset records (raw API data)
    master_record: Dict[str, Any] = Field(..., description="Master record from API")
    asset_record: Dict[str, Any] = Field(..., description="Asset record from API")

    @field_validator('dimensions')
    @classmethod
    def validate_dimensions(cls, v):
        if len(v) != 2 or v[0] <= 0 or v[1] <= 0:
            raise ValueError('Dimensions must be positive width x height')
        return v
```

**Why Pydantic (Correctly):**
- ✅ **External API Data**: Parsed from Apple Photos CloudKit API
- ✅ **Complex Validation**: Custom validators, ranges, date/time handling
- ✅ **JSON Serialization**: May be cached or exported

#### **PhotoAlbumInfo**
**Source:** `services/photos.py:PhotoAlbum` and album classes
**Purpose:** Photo album metadata
```python
class AlbumType(str, Enum):
    REGULAR = "regular"
    SMART = "smart"
    SHARED = "shared"
    FOLDER = "folder"

class PhotoAlbumInfo(BaseModel):
    name: str = Field(..., description="Album name")
    full_name: str = Field(..., description="Full album path")
    album_type: AlbumType = Field(..., description="Album type")

    # Album properties
    asset_count: int = Field(default=0, ge=0, description="Number of assets")
    list_type: str = Field(..., description="API list type")
    direction: str = Field(default="ASCENDING", description="Sort direction")

    # Smart album properties
    query_filter: Optional[List[Dict[str, Any]]] = Field(None, description="Smart album filter")
    obj_type: Optional[str] = Field(None, description="Object type filter")

    # Shared album properties
    sharing_type: Optional[str] = Field(None, description="Sharing type")
    is_public: bool = Field(default=False, description="Album is public")
    public_url: Optional[str] = Field(None, description="Public sharing URL")
    allow_contributions: bool = Field(default=False, description="Allow contributions")
```

### 3.2 Drive Service Models

#### **DriveNode**
**Source:** `services/drive.py:DriveNode` class
**Purpose:** File/folder representation from iCloud Drive API
```python
class DriveNodeType(str, Enum):
    FILE = "FILE"
    FOLDER = "FOLDER"
    ROOT = "ROOT"
    TRASH = "TRASH"
    UNKNOWN = "UNKNOWN"

class DriveNode(BaseModel):
    drivewsid: str = Field(..., description="Drive web service ID")
    docwsid: str = Field(..., description="Document web service ID")
    zone: str = Field(default="com.apple.CloudDocs", description="iCloud zone")

    # Basic properties
    name: str = Field(..., description="File/folder name")
    node_type: DriveNodeType = Field(..., description="Node type")
    etag: str = Field(..., description="Entity tag for versioning")

    # File properties (None for folders)
    size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    content_type: Optional[str] = Field(None, description="MIME content type")

    # Timestamps
    date_created: Optional[datetime] = Field(None, description="Creation date")
    date_modified: Optional[datetime] = Field(None, description="Last modification date")
    date_changed: Optional[datetime] = Field(None, description="Last change date")
    date_last_open: Optional[datetime] = Field(None, description="Last access date")

    # Hierarchy
    parent_id: Optional[str] = Field(None, description="Parent folder ID")
    children: List[str] = Field(default_factory=list, description="Child node IDs")

    # Raw API data
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Complete API response")
```

**Why Pydantic (Correctly):**
- ✅ **External API Data**: Parsed from iCloud Drive CloudKit API
- ✅ **Complex Validation**: File size constraints, enum validation
- ✅ **JSON Serialization**: Used for file metadata caching

### 3.3 Contacts Service Models

#### **ContactInfo**
**Source:** `services/contacts.py:ContactsService` and contact data
**Purpose:** Contact information
```python
class ContactInfo(BaseModel):
    contact_id: str = Field(..., description="Unique contact identifier")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")

    # Contact methods
    phone_numbers: List[Dict[str, str]] = Field(default_factory=list, description="Phone numbers")
    email_addresses: List[Dict[str, str]] = Field(default_factory=list, description="Email addresses")

    # Additional data
    organization: Optional[str] = Field(None, description="Organization/company")
    job_title: Optional[str] = Field(None, description="Job title")
    notes: Optional[str] = Field(None, description="Notes")

    # Photo
    has_photo: bool = Field(default=False, description="Contact has photo")
    photo_etag: Optional[str] = Field(None, description="Photo version tag")

    # Metadata
    created: Optional[datetime] = Field(None, description="Creation date")
    modified: Optional[datetime] = Field(None, description="Last modification date")
    etag: Optional[str] = Field(None, description="Contact version tag")

    # Raw API data
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Complete contact data")

    @property
    def full_name(self) -> str:
        """Get formatted full name"""
        parts = [self.first_name, self.last_name]
        return " ".join(part for part in parts if part)
```

### 3.4 Calendar Service Models

#### **CalendarEventInfo**
**Source:** `services/calendar.py:EventObject` dataclass
**Purpose:** Calendar event data
```python
class CalendarEventInfo(BaseModel):
    pguid: str = Field(..., description="Calendar GUID")
    guid: str = Field(..., description="Event GUID")
    title: str = Field(default="New Event", description="Event title")

    # Date/time
    start_date: datetime = Field(..., description="Event start time")
    end_date: datetime = Field(..., description="Event end time")
    local_start_date: Optional[datetime] = Field(None, description="Local start time")
    local_end_date: Optional[datetime] = Field(None, description="Local end time")
    all_day: bool = Field(default=False, description="All-day event")

    # Event properties
    location: Optional[str] = Field(None, description="Event location")
    timezone: str = Field(default="US/Pacific", description="Event timezone")
    duration: int = Field(..., ge=0, description="Duration in minutes")

    # Status flags
    is_junk: bool = Field(default=False, description="Junk event")
    recurrence_master: bool = Field(default=False, description="Is recurrence master")
    recurrence_exception: bool = Field(default=False, description="Is recurrence exception")

    # Attendees
    invitees: List[str] = Field(default_factory=list, description="Invitee email addresses")

    # Versioning
    etag: Optional[str] = Field(None, description="Event version tag")

    @field_validator('end_date')
    @classmethod
    def validate_end_after_start(cls, v, info):
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError('End date must be after start date')
        return v
```

#### **CalendarInfo**
**Source:** `services/calendar.py:CalendarObject` dataclass
**Purpose:** Calendar metadata
```python
class CalendarInfo(BaseModel):
    guid: str = Field(..., description="Calendar GUID")
    title: str = Field(default="Untitled", description="Calendar title")
    color: str = Field(..., description="Calendar color (hex)")

    # Calendar properties
    symbolic_color: str = Field(default="__custom__", description="Symbolic color")
    supported_type: str = Field(default="Event", description="Supported object type")
    object_type: str = Field(default="personal", description="Calendar type")
    order: int = Field(default=7, description="Display order")

    # Access control
    read_only: bool = Field(default=False, description="Read-only calendar")
    enabled: bool = Field(default=True, description="Calendar enabled")
    is_default: Optional[bool] = Field(None, description="Default calendar")
    is_family: Optional[bool] = Field(None, description="Family calendar")

    # Sharing
    share_type: Optional[str] = Field(None, description="Sharing type")
    shared_url: Optional[str] = Field(None, description="Shared URL")
    published_url: Optional[str] = Field(None, description="Published URL")

    # Versioning
    etag: Optional[str] = Field(None, description="Calendar version tag")
    ctag: Optional[str] = Field(None, description="Calendar collection tag")
```

### 3.5 Reminders Service Models

#### **ReminderInfo**
**Source:** `services/reminders.py:RemindersService` reminder data structure
**Purpose:** Individual reminder/task information
```python
class ReminderInfo(BaseModel):
    guid: str = Field(..., description="Unique reminder identifier")
    title: str = Field(..., description="Reminder title")
    description: Optional[str] = Field(None, description="Reminder description")

    # Due date handling
    due_date: Optional[datetime] = Field(None, description="Due date and time")
    due_date_is_all_day: bool = Field(default=False, description="All-day reminder")

    # Reminder properties
    priority: int = Field(default=0, ge=0, le=9, description="Priority level (0=none, 1=high, 9=low)")
    completed: bool = Field(default=False, description="Reminder completed")
    completed_date: Optional[datetime] = Field(None, description="Completion date")

    # Collection/list association
    collection_guid: str = Field(..., description="Parent collection GUID")

    # Metadata
    created_date: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified_date: Optional[datetime] = Field(None, description="Last modification")
    etag: Optional[str] = Field(None, description="Entity tag for versioning")

    # Advanced features
    alarms: List[Dict[str, Any]] = Field(default_factory=list, description="Reminder alarms")
    recurrence: Optional[Dict[str, Any]] = Field(None, description="Recurrence rules")
    is_family: Optional[bool] = Field(None, description="Family shared reminder")

class ReminderCollection(BaseModel):
    """Reminder list/collection information"""
    guid: str = Field(..., description="Collection unique identifier")
    title: str = Field(..., description="Collection name")
    ctag: str = Field(..., description="Collection tag for sync")

    # Collection properties
    color: Optional[str] = Field(None, description="Collection color")
    order: int = Field(default=0, description="Display order")
    is_default: bool = Field(default=False, description="Default collection")

    # Sharing
    is_shared: bool = Field(default=False, description="Shared collection")
    share_type: Optional[str] = Field(None, description="Sharing type")
```

### 3.6 Ubiquity Service Models

#### **UbiquityNodeInfo**
**Source:** `services/ubiquity.py:UbiquityNode` class
**Purpose:** Ubiquity document/file node information
```python
class UbiquityNodeType(str, Enum):
    FILE = "file"
    FOLDER = "folder"
    UNKNOWN = "unknown"

class UbiquityNodeInfo(BaseModel):
    item_id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Node name")
    node_type: UbiquityNodeType = Field(..., description="Node type")

    # File properties
    size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    modified: datetime = Field(..., description="Last modification date")

    # Hierarchy
    parent_id: Optional[str] = Field(None, description="Parent node ID")
    children_ids: List[str] = Field(default_factory=list, description="Child node IDs")

    # Raw API data for backward compatibility
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Complete node data")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or v == "<unknown>":
            raise ValueError('Node name cannot be empty or unknown')
        return v
```

### 3.7 Hide My Email Service Models

#### **EmailAliasInfo**
**Source:** `services/hidemyemail.py:HideMyEmailService` alias data
**Purpose:** Email alias information and metadata
```python
class AliasStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"

class EmailAliasInfo(BaseModel):
    anonymous_id: str = Field(..., description="Unique alias identifier")
    hme_email: str = Field(..., description="The alias email address")

    # Metadata
    label: str = Field(..., description="User-assigned label")
    note: Optional[str] = Field(None, description="Optional note")

    # Status and properties
    status: AliasStatus = Field(default=AliasStatus.ACTIVE, description="Alias status")
    is_active: bool = Field(default=True, description="Alias is active")

    # Timestamps
    created_date: Optional[datetime] = Field(None, description="Creation date")
    last_used_date: Optional[datetime] = Field(None, description="Last email received")

    # Usage statistics
    email_count: int = Field(default=0, ge=0, description="Number of emails received")

    # Domain and forwarding
    domain: str = Field(..., description="Email domain")
    forward_to_email: str = Field(..., description="Primary email for forwarding")

    # Raw API response for extensibility
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Complete alias data")

    @field_validator('hme_email')
    @classmethod
    def validate_email_format(cls, v):
        if '@' not in v or not v.endswith('@privaterelay.appleid.com'):
            raise ValueError('Invalid Hide My Email address format')
        return v

class EmailAliasGenerateRequest(BaseModel):
    """Request model for generating new email aliases"""
    label: str = Field(..., min_length=1, description="Label for the new alias")
    note: str = Field(default="Generated", description="Optional note")
    domain_preference: Optional[str] = Field(None, description="Preferred domain")

class EmailAliasUpdateRequest(BaseModel):
    """Request model for updating alias metadata"""
    anonymous_id: str = Field(..., description="Alias identifier")
    label: Optional[str] = Field(None, min_length=1, description="New label")
    note: Optional[str] = Field(None, description="New note")
```

### 3.8 Account Service Models

#### **AccountDeviceInfo**
**Source:** `services/account.py:AccountDevice` class
**Purpose:** Account-linked device information
```python
class AccountDeviceInfo(BaseModel):
    udid: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Device name")
    model: str = Field(..., description="Device model")
    model_display_name: str = Field(..., description="Display model name")

    # Device properties
    device_class: str = Field(..., description="Device class")
    platform: str = Field(..., description="Platform (iOS, macOS, etc.)")
    os_version: str = Field(..., description="Operating system version")

    # Status
    is_trusted: bool = Field(default=False, description="Trusted device")
    is_current_device: bool = Field(default=False, description="Current device")

    # Raw data
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Complete device data")
```

#### **FamilyMemberInfo**
**Source:** `services/account.py:FamilyMember` class
**Purpose:** Family member data
```python
class FamilyMemberInfo(BaseModel):
    dsid: str = Field(..., description="Directory Services ID")
    apple_id: str = Field(..., description="Apple ID email")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    full_name: Optional[str] = Field(None, description="Full name")

    # Family properties
    family_id: str = Field(..., description="Family group ID")
    age_classification: Optional[str] = Field(None, description="Age classification")
    has_parental_privileges: bool = Field(default=False, description="Has parental controls")
    has_screen_time_enabled: bool = Field(default=False, description="Screen time enabled")

    # Purchase settings
    apple_id_for_purchases: Optional[str] = Field(None, description="Purchase Apple ID")
    dsid_for_purchases: Optional[str] = Field(None, description="Purchase DSID")
    has_share_purchases_enabled: bool = Field(default=False, description="Share purchases")

    # Location sharing
    has_share_my_location_enabled: bool = Field(default=False, description="Location sharing enabled")
    share_my_location_enabled_family_members: List[str] = Field(default_factory=list, description="Members with location access")

    # Raw data
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Complete member data")
```

#### **StorageInfo**
**Source:** `services/account.py:AccountStorage` class
**Purpose:** iCloud storage information
```python
class StorageInfo(BaseModel):
    # Storage amounts (in bytes)
    total_storage_in_bytes: int = Field(..., ge=0, description="Total storage available")
    used_storage_in_bytes: int = Field(..., ge=0, description="Storage currently used")
    available_storage_in_bytes: int = Field(..., ge=0, description="Storage available")

    # Percentages
    used_storage_in_percent: float = Field(..., ge=0, le=100, description="Percent used")
    available_storage_in_percent: float = Field(..., ge=0, le=100, description="Percent available")

    # Quota information
    quota_over: bool = Field(default=False, description="Over storage quota")
    quota_almost_full: bool = Field(default=False, description="Quota almost full")
    quota_paid: bool = Field(default=False, description="Paid storage plan")
    quota_tier_max: int = Field(..., ge=0, description="Maximum quota tier")

    # Commerce
    commerce_storage_in_bytes: int = Field(default=0, ge=0, description="Commerce storage")
    comp_storage_in_bytes: int = Field(default=0, ge=0, description="Complementary storage")

    # Usage breakdown by media type
    usage_by_media: List[Dict[str, Any]] = Field(default_factory=list, description="Storage usage by media type")

    @field_validator('used_storage_in_bytes')
    @classmethod
    def validate_used_storage(cls, v, info):
        if 'total_storage_in_bytes' in info.data and v > info.data['total_storage_in_bytes']:
            raise ValueError('Used storage cannot exceed total storage')
        return v
```

---

## PRIORITY 4: CLI Configuration Models

### 4.1 CLI Command Models for Typer

#### **GlobalOptions**
**Source:** `cmdline.py:_create_parser` global arguments
**Purpose:** Global CLI configuration
```python
class LogLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    NONE = "none"

class GlobalOptions(BaseModel):
    # Authentication
    username: Optional[str] = Field(None, description="Apple ID username")
    password: Optional[str] = Field(None, description="Apple ID password")
    china_mainland: bool = Field(default=False, description="China mainland region")

    # Session behavior
    interactive: bool = Field(default=True, description="Enable interactive prompts")
    delete_from_keyring: bool = Field(default=False, description="Delete stored password")

    # Output/logging
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    debug: bool = Field(default=False, description="Enable debug logging")
    output_to_file: bool = Field(default=False, description="Save output to file")

    model_config = ConfigDict(
        json_schema_extra={
            "sensitive_fields": ["password"]
        }
    )
```

#### **DeviceCommands**
**Source:** `cmdline.py` device-related arguments
**Purpose:** Device management CLI commands
```python
class DeviceListOptions(BaseModel):
    list_short: bool = Field(default=False, description="Short device listing")
    list_long: bool = Field(default=False, description="Detailed device listing")
    device_id: Optional[str] = Field(None, description="Target specific device")

class DeviceActionOptions(BaseModel):
    device_id: Optional[str] = Field(None, description="Target device ID")

    # Sound/message actions
    play_sound: bool = Field(default=False, description="Play sound on device")
    message: Optional[str] = Field(None, description="Display message with sound")
    silent_message: Optional[str] = Field(None, description="Display message without sound")

    # Location
    locate: bool = Field(default=False, description="Get device location")

    # Lost mode
    lost_mode: bool = Field(default=False, description="Enable lost mode")
    lost_phone: Optional[str] = Field(None, description="Lost mode contact number")
    lost_password: Optional[str] = Field(None, description="Lost mode passcode")
    lost_message: str = Field(default="", description="Lost mode message")

    @field_validator('lost_phone')
    @classmethod
    def validate_phone_number(cls, v):
        if v and not v.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValueError('Invalid phone number format')
        return v
```

#### **OutputOptions**
**Source:** `cmdline.py` output formatting
**Purpose:** CLI output configuration
```python
class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"

class OutputOptions(BaseModel):
    format: OutputFormat = Field(default=OutputFormat.TABLE, description="Output format")
    output_file: Optional[str] = Field(None, description="Output file path")
    pretty: bool = Field(default=True, description="Pretty-print output")
    include_raw: bool = Field(default=False, description="Include raw API data")
```

### 4.2 Service-Specific CLI Models

#### **PhotosCommands**
**Source:** Future photos CLI functionality
**Purpose:** Photos service CLI operations
```python
class PhotosListOptions(BaseModel):
    album: Optional[str] = Field(None, description="Filter by album name")
    start_date: Optional[datetime] = Field(None, description="Filter from date")
    end_date: Optional[datetime] = Field(None, description="Filter to date")
    media_type: Optional[str] = Field(None, description="Filter by media type")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum results")

class PhotosDownloadOptions(BaseModel):
    album: Optional[str] = Field(None, description="Album to download")
    output_dir: str = Field(default="./downloads", description="Download directory")
    version: str = Field(default="original", description="Photo version")
    concurrent: int = Field(default=5, ge=1, le=20, description="Concurrent downloads")
```

#### **DriveCommands**
**Source:** Future drive CLI functionality
**Purpose:** iCloud Drive CLI operations
```python
class DriveListOptions(BaseModel):
    path: str = Field(default="/", description="Directory path to list")
    recursive: bool = Field(default=False, description="Recursive listing")
    show_hidden: bool = Field(default=False, description="Show hidden files")
    human_readable: bool = Field(default=True, description="Human-readable sizes")

class DriveUploadOptions(BaseModel):
    local_path: str = Field(..., description="Local file/directory path")
    remote_path: str = Field(default="/", description="Remote destination path")
    overwrite: bool = Field(default=False, description="Overwrite existing files")
    preserve_timestamps: bool = Field(default=True, description="Preserve file timestamps")
```

---

## PRIORITY 5: Advanced Service Models

### 5.1 Error and Exception Models

#### **CloudError**
**Source:** `exceptions.py` and error handling patterns
**Purpose:** Structured error information with serialization support
```python
class ErrorCode(str, Enum):
    AUTHENTICATION_REQUIRED = "auth_required"
    INVALID_CREDENTIALS = "invalid_credentials"
    TWO_FACTOR_REQUIRED = "2fa_required"
    SERVICE_UNAVAILABLE = "service_unavailable"
    NETWORK_ERROR = "network_error"
    RATE_LIMITED = "rate_limited"
    DEVICE_NOT_FOUND = "device_not_found"
    UNKNOWN_ERROR = "unknown_error"

class CloudError(BaseModel):
    code: ErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error context")
    retryable: bool = Field(default=False, description="Error can be retried")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error occurrence time")

    # Context information
    service: Optional[str] = Field(None, description="Service that generated error")
    operation: Optional[str] = Field(None, description="Operation that failed")
    http_status: Optional[int] = Field(None, description="HTTP status code")
```

**Why Pydantic (Correctly):**
- ✅ **Error Serialization**: May be logged as JSON or sent to error reporting
- ✅ **Rich Validation**: Enum validation, datetime handling
- ✅ **External Context**: Contains data from API responses/HTTP errors

### 5.2 Configuration and Settings Models

#### **PyiCloudConfig**
**Source:** Aggregate of configuration from multiple files
**Purpose:** Complete library configuration
```python
class PyiCloudConfig(BaseModel):
    # Authentication settings
    default_username: Optional[str] = Field(None, description="Default Apple ID")
    use_keyring: bool = Field(default=True, description="Use system keyring for passwords")
    china_mainland: bool = Field(default=False, description="China mainland region")

    # Session settings
    cookie_directory: Optional[str] = Field(None, description="Custom cookie directory")
    session_timeout: int = Field(default=3600, ge=60, description="Session timeout in seconds")
    auto_save_session: bool = Field(default=True, description="Auto-save session data")

    # Network settings
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    request_timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")

    # Feature flags
    enable_family_sharing: bool = Field(default=True, description="Include family data")
    enable_two_factor: bool = Field(default=True, description="Support 2FA/2SA")
    enable_logging: bool = Field(default=True, description="Enable request logging")

    # Service-specific settings
    photos_page_size: int = Field(default=100, ge=1, le=1000, description="Photos pagination size")
    drive_chunk_size: int = Field(default=8192, ge=1024, description="Drive upload chunk size")

    model_config = ConfigDict(
        json_schema_extra={
            "sensitive_fields": ["default_username"]
        }
    )
```

### 5.3 Event and Notification Models

#### **PyiCloudEvent**
**Source:** Observer pattern implementation needs
**Purpose:** Event system for extensibility
```python
class EventType(str, Enum):
    AUTHENTICATION_STARTED = "auth.started"
    AUTHENTICATION_SUCCESS = "auth.success"
    AUTHENTICATION_FAILED = "auth.failed"
    TWO_FACTOR_REQUIRED = "auth.2fa_required"
    DEVICE_LOCATED = "device.located"
    DEVICE_ACTION_STARTED = "device.action.started"
    DEVICE_ACTION_COMPLETED = "device.action.completed"
    SERVICE_ERROR = "service.error"
    SESSION_EXPIRED = "session.expired"

class PyiCloudEvent(BaseModel):
    event_type: EventType = Field(..., description="Event type")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    source: str = Field(..., description="Event source (service/component)")

    # Event data
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    user_id: Optional[str] = Field(None, description="Associated user/Apple ID")
    session_id: Optional[str] = Field(None, description="Associated session")

    # Metadata
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    severity: str = Field(default="info", description="Event severity")
```

---

## Implementation Plan

### **Phase 1: Foundation Models (Week 1)**

#### **File Organization Structure**
```
pyicloud/
├── models/
│   ├── __init__.py              # Public exports
│   ├── auth_dataclasses.py      # SrpPassword, AuthenticationContext
│   ├── session_dataclasses.py   # CookieJarConfig, internal configs
│   ├── session_models.py        # SessionData (Pydantic for persistence)
│   ├── auth_models.py           # TrustedDevice, API auth models
│   ├── service_models.py        # ServiceEndpoints, WebServiceInfo
│   ├── device_models.py         # Device management models
│   ├── api_models.py            # Complete API response models from spike
│   └── cli_models.py            # Typer CLI models (Phase 4)
```

#### **Concrete Deliverables**
1. **DC-1: SrpPassword → Dataclass** (1 day)
   ```python
   @dataclass
   class SrpPassword:
       password: str
       salt: bytes = field(init=False)
       iterations: int = field(init=False)
       key_length: int = field(init=False)

       def __post_init__(self) -> None:
           """Validate password is not empty."""
           if not self.password or not self.password.strip():
               raise ValueError("Password cannot be empty")

       def set_encrypt_info(self, salt: bytes, iterations: int, key_length: int) -> None:
           """Set encryption parameters with validation."""
           # ... validation logic

       def encode(self) -> bytes:
           """Encode password using PBKDF2-HMAC-SHA256."""
           # ... encoding logic
   ```

2. **DC-2: AuthenticationContext → Dataclass** (1 day)
3. **DC-3: CookieJarConfig → Dataclass** (0.5 day)

### **Phase 2: API Response Models (Week 2)**

#### **Priority: Missing Spike Models**
Based on cross-reference analysis, add these critical missing models:

1. **PM-1: Complete AccountLoginResponse Hierarchy** (2 days)
   - `AccountLoginResponse`, `DsInfo`, `Webservices`
   - `MailFlags`, `BeneficiaryInfo`, `AppleIdEntry`
   - `ConfigBag`, `Apps`, `RequestInfo`

2. **PM-2: FindMyDeviceResponse Models** (2 days)
   - `FindMyDeviceResponse`, `Device`, `ServerContext`
   - `MessageInfo`, `LocationInfo`, `LostDeviceInfo`
   - `SoundInfo`, `AudioChannel`, `UserInfo`

3. **PM-3: Authentication Models** (1 day)
   - `AppleAuthResponse`, `AppleHeaders` (with redaction)
   - `AccountLoginPayload`, `TrustedDevice`

### **Phase 3: Migration & Compatibility (Week 3)**

#### **Backward Compatibility Strategy**
```python
class PyiCloudService:
    def __init__(self, ...):
        # Internal: use typed models
        self._auth_context = AuthenticationContext(...)
        self._session_data = SessionData(...)

    @property
    def data(self) -> dict:
        """Legacy API: expose session as dict"""
        return self._session_data.model_dump()

    def __getitem__(self, key: str):
        """Legacy API: dict-style access"""
        return self.data[key]
```

#### **Migration Tools**
1. **Cookie Migration Script**: `scripts/migrate_sessions.py`
2. **Validation Script**: `scripts/validate_migration.py`
3. **Compatibility Tests**: Ensure all existing CLI examples work unchanged

### **Phase 4: Testing & Quality (Week 4)**

#### **Testing Requirements**
- **Coverage Target**: ≥95% for all new models
- **Performance Benchmarks**:
  - Load 1,000 realistic session JSONs → SessionData
  - Document median & 95th percentile vs raw dict
  - Target: <10% performance regression
- **Security Tests**: Verify sensitive field redaction
- **Integration Tests**: Real API calls with spike_architecture.py patterns

#### **Quality Gates**
```python
# Example benchmark test
def test_session_data_performance():
    """SessionData parsing should be within 10% of raw dict."""
    # Load 1000 realistic payloads
    times_dict = benchmark_dict_parsing(payloads)
    times_pydantic = benchmark_sessiondata_parsing(payloads)

    assert times_pydantic.median < times_dict.median * 1.1
```

### **Phase 5: Documentation & Examples (Week 5)**

#### **Documentation Deliverables**
1. **CONTRIBUTING.md**: Decision framework for dataclass vs Pydantic
2. **README.md**: Migration guide with before/after examples
3. **API Documentation**: Auto-generated from Pydantic models
4. **Example Scripts**:
   - `examples/legacy_flow.py` - Raw dict usage
   - `examples/typed_flow.py` - New typed models

#### **Decision Framework Documentation**
```markdown
## When to Use Dataclass vs Pydantic

### Use Dataclass ✅
- Internal-only data structures
- Performance-critical paths
- Simple validation sufficient
- No JSON serialization needed

### Use Pydantic ✅
- External API data
- Complex validation rules
- JSON serialization required
- Rich error messages needed

### Red Flags 🚩
- Dataclass with complex validation → Use Pydantic
- Pydantic for simple internal state → Use Dataclass
```

## Testing Strategy

### **Model Validation Tests**
```python
def test_srp_password_validation():
    """Test SrpPassword validation and error cases."""
    # Test empty password
    with pytest.raises(ValueError, match="Password cannot be empty"):
        SrpPassword("")

    # Test encode without setup
    srp = SrpPassword("valid_password")
    with pytest.raises(RuntimeError, match="Must call set_encrypt_info"):
        srp.encode()

def test_session_data_redaction():
    """Test sensitive field redaction in logs."""
    session = SessionData(session_token="secret123", client_id="public")

    # Capture log output
    with caplog.at_level(logging.INFO):
        logger.info("Session: %s", session)

    assert "secret123" not in caplog.text
    assert "***REDACTED***" in caplog.text
    assert "public" in caplog.text  # Non-sensitive field visible
```

### **Performance Benchmarks**
```python
@pytest.mark.benchmark
def test_device_features_performance():
    """DeviceFeatures dataclass should be faster than Pydantic equivalent."""

    # Benchmark dataclass creation
    time_dataclass = timeit.timeit(
        lambda: DeviceFeatures(LOC=True, SND=False),
        number=10000
    )

    # Benchmark equivalent Pydantic model
    time_pydantic = timeit.timeit(
        lambda: DeviceFeaturesModel(LOC=True, SND=False),
        number=10000
    )

    # Dataclass should be significantly faster
    assert time_dataclass < time_pydantic * 0.5
```

### **Migration Compatibility Tests**
```python
def test_backward_compatibility():
    """Ensure legacy dict access patterns still work."""
    service = PyiCloudService(apple_id="test@example.com", password="test")

    # Legacy patterns that must continue working
    assert service.data["client_id"] == service._session_data.client_id
    assert service["client_id"] == service._session_data.client_id
    assert "session_token" in service.data
```

## Success Criteria

### **Functional Requirements**
- ✅ All existing CLI examples work unchanged
- ✅ Session persistence maintains compatibility
- ✅ Device management APIs unchanged
- ✅ Error messages improved with structured validation

### **Performance Requirements**
- ✅ <10% performance regression on critical paths
- ✅ Memory usage comparable or better
- ✅ Startup time within 5% of current

### **Quality Requirements**
- ✅ ≥95% test coverage on new models
- ✅ All sensitive fields redacted in logs
- ✅ Type checking passes with mypy strict mode
- ✅ Documentation complete with examples

---

## Implementation Strategy

### Phase 1: Core Authentication & Session Models
1. Implement authentication and session models
2. Create backward-compatible wrappers for existing `PyiCloudService`
3. Add internal validation while maintaining dict access
4. Test with real Apple API responses

### Phase 2: Device Management (Priority 2)
1. Implement device and location models
2. Enhance `AppleDevice` class with Pydantic validation
3. Add type-safe device action methods
4. Maintain existing property access patterns

### Phase 3: Service Models (Priority 3)
1. Implement service-specific response models
2. Add validation to service classes
3. Create typed service factories
4. Provide both typed and dict access patterns

### Phase 4: CLI Modernization (Priority 4)
1. Migrate `cmdline.py` from argparse to Typer
2. Implement CLI configuration models
3. Add JSON/YAML output formats
4. Create command-specific validation

### Phase 5: Advanced Features (Priority 5)
1. Implement error handling models
2. Add configuration management
3. Create event system for extensibility
4. Add comprehensive logging models

## Backward Compatibility Strategy

### Wrapper Pattern
```python
class AppleDeviceCompat:
    def __init__(self, device_info: AppleDeviceInfo):
        self._info = device_info
        self._content = device_info.raw_data  # Original dict access

    @property
    def name(self) -> str:
        return self._info.name  # Typed access

    def __getitem__(self, key):
        return self._content[key]  # Legacy dict access

    @property
    def data(self) -> dict:
        return self._content  # Full backward compatibility
```

### Migration Helpers
```python
def migrate_device_data(old_dict: dict) -> AppleDeviceInfo:
    """Convert legacy device dict to Pydantic model"""
    return AppleDeviceInfo.model_validate(old_dict)

def ensure_compatibility(response: dict) -> Tuple[dict, AppleDeviceInfo]:
    """Return both dict and typed versions"""
    typed = AppleDeviceInfo.model_validate(response)
    return response, typed
```

## Testing Strategy

### Model Validation Tests
- Test all field validations and constraints
- Test model serialization/deserialization
- Test backward compatibility wrappers
- Test error handling and edge cases

### Integration Tests
- Test with real Apple API responses (redacted)
- Test service integration with new models
- Test CLI command parsing and validation
- Test session management and persistence

### Performance Tests
- Benchmark model validation overhead
- Test memory usage with large datasets
- Verify no regression in API call performance
- Test concurrent model operations

## Documentation Plan

### API Documentation
- Generate comprehensive API docs from Pydantic models
- Create migration guide for existing users
- Document all backward compatibility guarantees
- Provide examples for common use cases

### Developer Documentation
- Internal architecture documentation
- Model design patterns and rationale
- Testing and validation guidelines
- Contributing guidelines for new models

---

## Summary

This analysis identifies **85+ distinct Pydantic models** across 5 priority levels, providing comprehensive type safety, validation, and modern Python patterns while maintaining full backward compatibility.

**⚠️ Important**: Cross-reference with `spike_architecture.py` reveals **34 critical working models are missing** from this analysis, particularly comprehensive authentication, session management, and API response models that have been validated against real Apple APIs. These gaps must be addressed for complete coverage.

The implementation will significantly improve:

- **Type Safety**: Comprehensive typing for all API responses
- **Validation**: Automatic validation of Apple API data
- **Documentation**: Self-documenting models with field descriptions
- **Developer Experience**: Better IDE support and error messages
- **CLI Modernization**: Typer-based CLI with structured configuration
- **Error Handling**: Structured error information and debugging
- **Testing**: Type-safe test data generation and validation

The phased implementation approach ensures minimal disruption to existing users while providing a clear migration path to modern Python development patterns.

## Model Selection Summary

### **Dataclass Models (7 models)**
*Performance-optimized internal structures*

| Model | Purpose | Why Dataclass |
|-------|---------|---------------|
| `SrpPassword` | SRP encryption state | Internal crypto, two-phase init |
| `AuthenticationContext` | Auth state management | Internal only, high frequency |
| `CookieJarConfig` | Cookie configuration | Simple config, no serialization |
| `DeviceFeatures` | Device capability flags | High frequency access, simple flags |
| `PlaySoundRequest` | Device action params | Internal request, no serialization |
| `DisplayMessageRequest` | Device action params | Internal request, no serialization |
| `LostModeRequest` | Device action params | Internal request, no serialization |

### **Pydantic Models (78+ models)**
*API integration and validation-heavy structures*

| Category | Count | Examples | Why Pydantic |
|----------|-------|----------|--------------|
| **API Response Models** | 45+ | `AppleDeviceInfo`, `PhotoAsset`, `DriveNode` | External data, JSON parsing |
| **API Request Models** | 15+ | `TrustedDevice`, `AccountLoginPayload` | External data, validation |
| **CLI Models** | 10+ | `GlobalOptions`, `DeviceCommands` | External input, complex validation |
| **Config Models** | 5+ | `PyiCloudConfig`, `SessionData` | File parsing, serialization |
| **Error Models** | 3+ | `CloudError`, `PyiCloudEvent` | Serialization, rich validation |

### **Hybrid Pattern: Dataclass + Pydantic Adapter**

For performance-critical models that also need API parsing:

```python
# Internal performance-optimized version
@dataclass
class DeviceFeatures:
    LOC: Optional[bool] = None
    # ... other flags

# API parsing adapter
class DeviceFeaturesModel(BaseModel):
    LOC: Optional[bool] = None
    # ... same fields

    def to_dataclass(self) -> DeviceFeatures:
        return DeviceFeatures(**self.model_dump())
```

## Future Model Guidelines

### **Choose Dataclass When:**
- ✅ Used only within PyiCloud internals
- ✅ Simple type validation sufficient
- ✅ High-frequency object creation
- ✅ No JSON serialization needed
- ✅ Performance is measurably important

### **Choose Pydantic When:**
- ✅ Data crosses any boundary (API, file, CLI, network)
- ✅ Complex validation rules needed
- ✅ JSON serialization required
- ✅ Rich error messages important
- ✅ Auto-documentation desired

### **Red Flags - Reconsider Choice:**
- ❌ Dataclass with complex validation logic → Use Pydantic
- ❌ Pydantic for simple internal state → Use Dataclass
- ❌ Manual JSON parsing in dataclass → Use Pydantic
- ❌ Performance issues with Pydantic → Consider Dataclass + Adapter

## Cross-Reference: Spike Architecture Models vs Analysis

This section cross-references the working Pydantic models implemented in `spike_architecture.py` against the models documented in this analysis to ensure complete coverage and identify any gaps.

### ✅ **Models Present in Both Spike and Analysis**

#### Priority 2: Device Management Models
- ✅ `DeviceFeatures` → **AppleDeviceInfo.features** (analysis line 177)
- ✅ `BatteryStatus` → **BatteryStatus enum** (analysis line 165)
- ✅ `DeviceStatus` → **DeviceStatus enum** (analysis line 171)
- ✅ `DeviceLocation` → **DeviceLocation** (analysis line 215)
- ✅ `PositionType` → **PositionType enum** (analysis line 220)

#### Priority 5: Error and Configuration Models
- ✅ `CloudError` → **CloudError** (analysis line 866)
- ✅ `CloudErrorCode` → **ErrorCode enum** (analysis line 868)

### ❌ **Critical Models Missing from Analysis**

#### **Priority 1: Authentication & Session Models (High Impact)**

**From spike `AccountLoginPayload`** - Missing comprehensive account login model:
```python
class AccountLoginPayload(BaseModel):
    accountCountryCode: str = Field(..., pattern=r"^[A-Z]{3}$")
    dsWebAuthToken: str = Field(...)
    extended_login: bool = Field(...)
    trustToken: str = Field(...)
```

**From spike `AppleAuthResponse`** - Missing authentication response validation:
```python
class AppleAuthResponse(BaseModel):
    authType: Optional[str] = None
    sessionToken: Optional[str] = Field(None, json_schema_extra={"sensitive": True})
    dsWebAuthToken: Optional[str] = Field(None, json_schema_extra={"sensitive": True})
    # ... with redaction metadata
```

**From spike `AppleHeaders`** - Missing header validation and redaction:
```python
class AppleHeaders(BaseModel):
    session_token: Optional[str] = Field(None, alias="X-Apple-Session-Token", json_schema_extra={"sensitive": True})
    session_id: Optional[str] = Field(None, alias="X-Apple-ID-Session-Id", json_schema_extra={"sensitive": True})
    # ... comprehensive header handling
```

#### **Priority 1: Complete Account Response Models (High Impact)**

**From spike `AccountLoginResponse`** - Missing comprehensive iCloud service response:
```python
class AccountLoginResponse(BaseModel):
    dsInfo: DsInfo
    webservices: Webservices
    configBag: ConfigBag
    apps: Apps
    # ... 20+ additional fields from real API
```

**Supporting models missing:**
- `DsInfo` - Directory Services information (50+ fields)
- `Webservices` - All iCloud service endpoints
- `MailFlags` - Email service configuration
- `BeneficiaryInfo` - Account beneficiary data
- `AppleIdEntry` - Apple ID entry information
- `ConfigBag` & `ConfigBagUrls` - Service configuration
- `Apps` & `AppInfo` - App availability and features
- `RequestInfo` - Request context
- `ICloudInfo` - iCloud-specific settings

#### **Priority 2: Find My iPhone Response Models (High Impact)**

**From spike `FindMyDeviceResponse`** - Missing complete device response structure:
```python
class FindMyDeviceResponse(BaseModel):
    content: List[Device]
    serverContext: ServerContext
    userInfo: UserInfo
    userPreferences: UserPreferences
    # ... complete API response structure
```

**Supporting models missing:**
- `Device` - Complete device model (40+ fields)
- `ServerContext` - Server configuration (30+ fields)
- `UserInfo` - User account information
- `MessageInfo` - Device message data
- `LocationInfo` - Complete location information
- `LostDeviceInfo` - Lost mode configuration
- `SoundInfo` - Sound alert information
- `AudioChannel` - Audio channel data
- `TheftLoss` & `AwarenessString` - Security features
- `Timezone` - Timezone information
- `UserPreferences` & `WebPrefs` - User settings

#### **Priority 3: Architecture Pattern Models (Medium Impact)**

**From spike pattern implementations:**
- `AuthContext` - Authentication state encapsulation
- `AppleCredentials` - Credential chain foundation
- `OperationModel` - Service operation definitions
- `ServiceModel` - Service configuration model
- `Success` & `Failure` - Result pattern implementations

### 📝 **Models Unique to Analysis (Not in Spike)**

#### Service-Specific Models (Correctly planned but not spike-implemented):
- **Photos Service**: `PhotoAsset`, `PhotoAlbumInfo`
- **Drive Service**: `DriveNode`
- **Contacts Service**: `ContactInfo`
- **Calendar Service**: `CalendarEventInfo`, `CalendarInfo`
- **Account Service**: `AccountDeviceInfo`, `FamilyMemberInfo`, `StorageInfo`
- **Reminders Service**: `ReminderInfo`, `ReminderCollection`
- **Ubiquity Service**: `UbiquityNodeInfo`
- **Hide My Email Service**: `EmailAliasInfo`
- **CLI Models**: All Typer-related configuration models

### 🔧 **Recommended Actions**

#### **Immediate (Priority 1)**
1. **Add missing authentication models** to analysis Priority 1 section
2. **Add complete AccountLoginResponse hierarchy** (15+ models)
3. **Add AppleAuthResponse and AppleHeaders** with redaction metadata
4. **Add Result pattern models** (Success/Failure/AuthContext)

#### **High Priority (Priority 2)**
1. **Add complete FindMyDeviceResponse hierarchy** (12+ models)
2. **Add Device model** with all 40+ real API fields
3. **Add ServerContext and UserInfo** models
4. **Add architecture pattern models** (OperationModel, ServiceModel)

#### **Medium Priority (Priority 3)**
1. **Enhance existing device models** with missing audio/security fields
2. **Add validation patterns** from spike implementations
3. **Add redaction strategy models** for security

### 📊 **Coverage Summary**

- **Spike Models**: 41 distinct models (33 BaseModel + 6 Enum + 2 dataclass)
- **Analysis Models**: 85+ planned models
- **Overlap**: ~7 models (17% coverage of spike models)
- **Analysis Gaps**: ~34 critical models missing (83% of working spike models)

**Conclusion**: The analysis document needs significant expansion to include the proven working models from the spike architecture, particularly the comprehensive authentication, session management, and API response models that have been validated against real Apple API responses.
