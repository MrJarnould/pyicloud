# **📋 Sprint #1: PolicyExecutor Pattern Extraction from CloudClient**

*Spike refactoring plan to extract retry/circuit-breaker logic using Strategy pattern and dependency injection*

## **🎯 Sprint #1 Goals & Pattern Demonstration**

**Epic:** Extract retry/circuit-breaker logic from `_execute_http_request` (lines 1534-1581) into PolicyExecutor Strategy pattern, enabling dependency injection while preserving spike's behavioral demonstrations.

## **🎯 Sprint #1 Scope Boundaries**

**What Sprint #1 Achieves:**
- ✅ **Strategy Pattern Implementation**: Extract retry logic into PolicyExecutor interface
- ✅ **Dependency Injection**: Inject retry policies into CloudClient via constructor
- ✅ **Factory Method Pattern**: Implement CloudError factory methods for categorization
- ✅ **Offline Testing**: Enable deterministic testing with zero sleeps (NoRetryPolicy)
- ✅ **Performance Improvement**: Eliminate per-call allocations (`_Retryable` class + `_run()` function)
- ✅ **Mathematical Parity**: Contract tests prove behavioral equivalence to current `@backoff`

**What Sprint #1 Does NOT Achieve:**
- ❌ **Full SOLID Compliance**: CloudClient still violates Single Responsibility Principle
- ❌ **Complete Separation of Concerns**: CloudClient retains 8+ distinct responsibilities
- ❌ **Production Readiness**: This is a spike for GoF pattern demonstration
- ❌ **Comprehensive Architecture**: Additional sprints required for full SOLID compliance

**Sprint #1 Success Criteria:**
- ✅ **Pattern Validation**: Strategy pattern cleanly separates retry concerns
- ✅ **Behavioral Preservation**: Spike's existing Apple API demonstrations continue working
- ✅ **Interface Stability**: Spike's public APIs remain unchanged for future sprints
- ✅ **Performance Measurement**: 70%+ reduction in retry path memory allocations
- ✅ **Testing Enhancement**: Zero-sleep deterministic test execution capability

## **🔮 Post-Sprint #1 Architecture State**

**CloudClient will still contain multiple responsibilities requiring future sprints:**

1. **Operation Management**: Validate operations, lookup from service model
2. **Authentication Coordination**: Get auth context, handle auth failures
3. **Protocol Orchestration**: Select and manage protocol handlers
4. **HTTP Communication**: Execute requests, handle transport errors
5. **Response Processing**: Deserialize responses, handle semantic errors
6. **Event Management**: Emit before/after operation events
7. **Session Management**: Get authenticated sessions from auth provider
8. **Parameter Construction**: Build request parameters (DSID, etc.)
9. **Request Logging**: Log request details with redaction

**Multiple Reasons CloudClient Will Still Change:**
- Changes in operation validation logic → requires modification
- Changes in authentication flow → requires modification
- Changes in protocol handling → requires modification
- Changes in HTTP communication patterns → requires modification
- Changes in error categorization rules → requires modification
- Changes in event system design → requires modification
- Changes in logging requirements → requires modification

**Future Sprints Required for Full SOLID Compliance:**
- **Sprint #2**: Extract HTTP execution into dedicated HttpExecutor
- **Sprint #3**: Extract request/response processing into specialized handlers
- **Sprint #4**: Extract operation management and authentication coordination
- **Sprint #N**: Continue until CloudClient becomes thin orchestration layer

## **🔍 Codebase Reality Assessment**

### **Current Spike Analysis (`spike_architecture.py`):**
- **File size**: 1,831 lines demonstrating GoF patterns and SOLID principles
- **Retry extraction target**: Lines 1534-1581 in `CloudClient._execute_http_request`
- **Performance bottleneck**: Per-call allocation of `_Retryable` class and `_run()` function
- **CloudError usage**: @dataclass implementation (line 887), 17 manual constructor calls requiring factory migration
- **Natural separation boundary**: `_make_http_request` (transport) vs `_handle_response` (semantic)
- **Architecture foundation**: CloudSession → CloudClient → AuthenticationProvider dependency chain established

### **CloudError Construction Sites Analysis:**
```bash
# Actual locations requiring factory migration (confirmed via grep)
grep -n "CloudError(" spike_architecture.py
```
**All 17 CloudError constructor calls:**
- Line 1206: `CloudError(code=CloudErrorCode.AUTHENTICATION_REQUIRED, ...)`
- Line 1220: `CloudError(code=CloudErrorCode.AUTHENTICATION_REQUIRED, ...)`
- Line 1255: `CloudError(code=CloudErrorCode.TWO_FACTOR_REQUIRED, ...)`
- Line 1265: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1277: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1339: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1353: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1430: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1451: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1505: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1575: `CloudError(code=CloudErrorCode.NETWORK_ERROR, ...)`
- Line 1603: `CloudError(code=CloudErrorCode.UNKNOWN, ...)`
- Line 1640: `CloudError(code=CloudErrorCode.*, ...)`  # Dynamic error code
- Line 1680: `CloudError(code=CloudErrorCode.AUTHENTICATION_REQUIRED, ...)`
- Line 1697: `CloudError(code=CloudErrorCode.AUTHENTICATION_REQUIRED, ...)`
- Line 1708: `CloudError(code=CloudErrorCode.AUTHENTICATION_REQUIRED, ...)`
- Line 1722: `CloudError(code=CloudErrorCode.SERVICE_UNAVAILABLE, ...)`

### **Current Retry Logic Requiring Extraction:**
```python
# Lines 1534-1581: Strategy pattern extraction target
class _Retryable(Exception):  # ← VIOLATION: Per-call allocation, mixed concerns
    def __init__(self, ce: CloudError):
        super().__init__(ce.message)
        self.ce = ce

@backoff.on_exception(
    backoff.expo,
    (_Retryable, requests.RequestException),
    max_tries=max(1, operation.retry_count),
    jitter=backoff.full_jitter,
    factor=0.5,  # base delay (0.5s, 1s, 2s, 4s...)
)
def _run() -> Result[bytes, CloudError]:  # ← VIOLATION: Nested function allocation
    # Mixed concerns: retry logic embedded in HTTP execution method
    # Target for Strategy pattern extraction
```

## **🏗️ Target Architecture (Post-Sprint #1)**

```
CloudSession
├── PolicyRegistry (immutable interface, startup validation)
│   ├── DEFAULT_POLICY_NAME = "default_backoff"
│   ├── DefaultBackoffPolicy (exact @backoff mathematical parity)
│   ├── NoRetryPolicy (zero-sleep deterministic testing)
│   └── Custom policies (extensible Strategy pattern)
├── AuthenticationProvider (unchanged - future sprint concern)
└── ProtocolHandlers (unchanged - future sprint concern)

CloudClient (STILL VIOLATES SRP - requires future sprints)
├── PolicyExecutor (NEW: injected Strategy) → execute(ctx, attempt_func)
├── ServiceModel (unchanged - mixed concern)
├── EventBus (unchanged - mixed concern)
├── AuthenticationCoordination (unchanged - mixed concern)
├── ProtocolOrchestration (unchanged - mixed concern)
├── SessionManagement (unchanged - mixed concern)
├── RequestLogging (unchanged - mixed concern)
└── ParameterConstruction (unchanged - mixed concern)

Flow: invoke_operation → _make_real_http_call → policy_executor.execute(ctx, _single_attempt)
                                                                              ↓
                                                                   _make_http_request → _handle_response
```

**Strategy Pattern Implementation:**
- **Context**: CloudClient delegates retry decisions to PolicyExecutor
- **Strategy Interface**: PolicyExecutor protocol with execute() method
- **Concrete Strategies**: DefaultBackoffPolicy, NoRetryPolicy, custom policies
- **Strategy Selection**: Via PolicyRegistry dependency injection

## **📦 Core Components Design**

### **V8-1: Error Category & Factory Methods**

```python
# Insert after line 873 (before CloudError definition)
import time
from enum import Enum
from abc import ABC, abstractmethod
from typing import Protocol, Callable, List, Optional

class ErrorCategory(Enum):
    """Categorize errors by their nature for policy decisions"""
    TRANSPORT = "transport"    # Network failures, timeouts, connection issues
    SEMANTIC = "semantic"      # HTTP status codes, API business logic responses

# Enhance existing CloudError @dataclass (line 887)
@dataclass
class CloudError:
    """Structured error with category-aware factory methods"""
    code: CloudErrorCode
    message: str
    details: Dict[str, Any]
    retryable: bool = False
    category: ErrorCategory = ErrorCategory.SEMANTIC  # Backwards compatible default

    @classmethod
    def transport(cls,
                  code: CloudErrorCode,
                  message: str,
                  details: Optional[Dict[str, Any]] = None,
                  retryable: Optional[bool] = None) -> 'CloudError':
        """Factory for network-level failures

        Transport errors are typically retryable as they indicate infrastructure
        issues rather than application logic problems.

        Args:
            code: CloudErrorCode enum value
            message: Human-readable error description
            details: Optional context dictionary
            retryable: Override default retryable behavior (DISCOURAGED - use semantic() for non-retryable)

        Raises:
            ValueError: If retryable=False conflicts with transport error semantics
        """
        # Validate semantic consistency - transport errors should generally be retryable
        final_retryable = True if retryable is None else retryable
        if retryable is False:
            import warnings
            warnings.warn(
                f"Transport error marked as non-retryable: {message}. "
                "Consider using CloudError.semantic() for non-retryable errors.",
                UserWarning,
                stacklevel=2
            )

        return cls(
            code=code,
            message=message,
            details=details or {},
            category=ErrorCategory.TRANSPORT,
            retryable=final_retryable
        )

    @classmethod
    def semantic(cls,
                 code: CloudErrorCode,
                 message: str,
                 details: Optional[Dict[str, Any]] = None,
                 retryable: Optional[bool] = None) -> 'CloudError':
        """Factory for application-level failures

        Semantic errors typically represent business logic failures and are
        not retryable unless explicitly marked (e.g., 5xx status codes).

        Args:
            code: CloudErrorCode enum value
            message: Human-readable error description
            details: Optional context dictionary
            retryable: Override default retryable behavior (DISCOURAGED - use semantic_retryable() for retryable)

        Raises:
            ValueError: If retryable=True conflicts with semantic error semantics
        """
        # Validate semantic consistency - semantic errors should generally not be retryable
        final_retryable = False if retryable is None else retryable
        if retryable is True:
            import warnings
            warnings.warn(
                f"Semantic error marked as retryable: {message}. "
                "Consider using CloudError.semantic_retryable() for retryable semantic errors.",
                UserWarning,
                stacklevel=2
            )

        return cls(
            code=code,
            message=message,
            details=details or {},
            category=ErrorCategory.SEMANTIC,
            retryable=final_retryable
        )

    @classmethod
    def semantic_retryable(cls,
                          code: CloudErrorCode,
                          message: str,
                          details: Optional[Dict[str, Any]] = None) -> 'CloudError':
        """Factory for retryable semantic errors (5xx, 429 status codes)

        Special case for server-side errors that should be retried despite
        being at the semantic layer. Does not accept retryable parameter to
        prevent confusion - these are always retryable by definition.
        """
        return cls(
            code=code,
            message=message,
            details=details or {},
            category=ErrorCategory.SEMANTIC,
            retryable=True
        )
```

### **V8-2: Policy Infrastructure**

```python
# Insert after ErrorCategory definition

@dataclass
class PolicyContext:
    """Context passed to policies containing execution state

    IMPORTANT: attempt_no uses 0-based indexing:
    - 0 = first attempt (initial call)
    - 1 = first retry
    - 2 = second retry, etc.

    This differs from user-facing log messages which use 1-based counting
    for clarity (e.g., "Retry 1/3" for attempt_no=1).
    """
    operation: OperationModel
    attempt_no: int = 0           # 0-based: 0=first attempt, 1=first retry, etc.
    last_error: Optional[CloudError] = None
    url: str = ""                 # Request URL for logging/debugging

class PolicyExecutor(Protocol):
    """Strategy interface for retry/circuit-breaker policies

    Note: @abstractmethod decorators are technically redundant with Protocol
    structural typing, but provide valuable IDE support and documentation.
    The runtime behavior is identical - methods are checked structurally.
    """

    @abstractmethod
    def execute(self,
                ctx: PolicyContext,
                attempt: Callable[[], Result[bytes, CloudError]]) -> Result[bytes, CloudError]:
        """Execute operation with policy-specific retry logic

        Args:
            ctx: Policy execution context with operation details
            attempt: Idempotent function to execute (single HTTP attempt)

        Returns:
            Result containing success bytes or final error after policy execution
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Policy identifier for logging and debugging"""
        pass

class DefaultBackoffPolicy(PolicyExecutor):
    """Extracts current @backoff logic with exact mathematical parity

    Implements: @backoff.on_exception(backoff.expo, factor=0.5, jitter=backoff.full_jitter)

    Mathematical sequence (0-based attempt_no):
    - attempt_no=0: base_delay * 2^0 = 0.5s + jitter
    - attempt_no=1: base_delay * 2^1 = 1.0s + jitter
    - attempt_no=2: base_delay * 2^2 = 2.0s + jitter
    - attempt_no=3: base_delay * 2^3 = 4.0s + jitter
    """

    def __init__(self,
                 base_delay: float = 0.5,
                 max_delay: float = 60.0,
                 jitter_func: Callable[[float], float] = backoff.full_jitter,
                 sleep_func: Callable[[float], None] = time.sleep):
        """Initialize with configurable parameters

        Args:
            base_delay: Factor parameter from @backoff (0.5 seconds)
            max_delay: Maximum delay cap in seconds
            jitter_func: Jitter function (default: backoff.full_jitter)
            sleep_func: Sleep implementation (injectable for testing)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_func = jitter_func
        self.sleep_func = sleep_func

    @property
    def name(self) -> str:
        return PolicyRegistry.DEFAULT_POLICY_NAME

    def execute(self,
                ctx: PolicyContext,
                attempt: Callable[[], Result[bytes, CloudError]]) -> Result[bytes, CloudError]:
        """Execute with exponential backoff - exact @backoff parity"""
        max_tries = max(1, ctx.operation.retry_count)
        last_result = None

        for attempt_no in range(max_tries):
            # IMPORTANT: Set attempt_no BEFORE calling attempt() so any introspection
            # sees the current attempt number (0=first, 1=first retry, etc.)
            ctx.attempt_no = attempt_no
            result = attempt()
            last_result = result

            if result.is_success:
                if attempt_no > 0:
                    # Log with 1-based counting for user clarity: attempt 2/3 means first retry
                    logger.info("✅ Retry succeeded on attempt %d/%d (%s)",
                              attempt_no + 1, max_tries, self.name)
                return result

            # Store error for policy decision and potential next iteration
            ctx.last_error = result.error

            # Policy decision: should we retry?
            if not self._should_retry(result.error, attempt_no, max_tries):
                break

            # Calculate delay with exact @backoff mathematical parity
            operation_max_delay = getattr(ctx.operation, 'max_delay', None) or self.max_delay
            exponential_delay = self.base_delay * (2 ** attempt_no)
            capped_delay = min(exponential_delay, operation_max_delay)
            jittered_delay = self.jitter_func(capped_delay)

            # Log with 1-based counting for user clarity
            logger.debug("🔄 Retry %d/%d after %.3fs delay (%s) for %s",
                        attempt_no + 1, max_tries, jittered_delay, self.name, ctx.operation.name)
            self.sleep_func(jittered_delay)

        # Exhausted all retry attempts
        logger.error("❌ Exhausted retries for %s using %s", ctx.operation.name, self.name)
        return last_result

    def _should_retry(self, error: CloudError, attempt_no: int, max_tries: int) -> bool:
        """Policy logic preserving exact current behavior

        Current logic from _execute_http_request:
        - Only retry if error.retryable is True
        - Never exceed max_tries

        Args:
            error: The error from the failed attempt
            attempt_no: 0-based attempt number (0=first attempt, 1=first retry)
            max_tries: Maximum attempts allowed
        """
        return attempt_no + 1 < max_tries and error.retryable

class NoRetryPolicy(PolicyExecutor):
    """Deterministic policy for testing - single attempt, zero sleeps"""

    @property
    def name(self) -> str:
        return "no_retry"

    def execute(self,
                ctx: PolicyContext,
                attempt: Callable[[], Result[bytes, CloudError]]) -> Result[bytes, CloudError]:
        """Single attempt execution - deterministic for testing"""
        ctx.attempt_no = 0  # Always first (and only) attempt
        result = attempt()

        if result.is_failure:
            logger.debug("❌ No retry policy - failing immediately for %s", ctx.operation.name)

        return result

class FakeSleeper:
    """Test utility for capturing and validating sleep behavior"""

    def __init__(self):
        self.calls: List[float] = []
        self._total: float = 0.0

    def sleep(self, duration: float) -> None:
        """Record sleep duration instead of actually sleeping"""
        self.calls.append(duration)
        self._total += duration

    @property
    def total_sleep(self) -> float:
        """Total sleep time across all calls"""
        return self._total

    @property
    def call_count(self) -> int:
        """Number of sleep calls made"""
        return len(self.calls)

    def reset(self) -> None:
        """Clear all recorded calls"""
        self.calls.clear()
        self._total = 0.0

    def assert_no_sleeps(self) -> None:
        """Test assertion: verify zero sleep calls"""
        assert len(self.calls) == 0, f"Expected no sleeps, but got {self.calls}"

    def assert_sleep_sequence(self, expected: List[float], tolerance: float = 0.01) -> None:
        """Test assertion: verify exact sleep sequence"""
        assert len(self.calls) == len(expected), \
            f"Expected {len(expected)} sleeps, got {len(self.calls)}: {self.calls}"

        for i, (actual, expected_val) in enumerate(zip(self.calls, expected)):
            assert abs(actual - expected_val) <= tolerance, \
                f"Sleep {i}: expected ~{expected_val:.3f}s, got {actual:.3f}s"
```

### **V8-3: Registry with Startup Validation**

```python
class PolicyRegistry:
    """Centralized policy management with immutable interface and startup validation"""

    # Single source of truth for default policy name
    DEFAULT_POLICY_NAME = "default_backoff"

    def __init__(self,
                 default_policy: PolicyExecutor,
                 policies: Optional[Dict[str, PolicyExecutor]] = None):
        """Initialize registry with comprehensive startup validation

        Args:
            default_policy: Fallback policy (typically DefaultBackoffPolicy)
            policies: Additional policies by name (optional)

        Raises:
            ValueError: If policy configuration is invalid
            TypeError: If policies don't implement required interface
        """
        self._default_policy = default_policy
        self._policies = dict(policies or {})

        # Always register default under canonical name
        self._policies[self.DEFAULT_POLICY_NAME] = default_policy

        # Handle duplicate policy registration with warning
        if policies and self.DEFAULT_POLICY_NAME in policies:
            provided_default = policies[self.DEFAULT_POLICY_NAME]
            if provided_default != default_policy:
                logger.warning(
                    f"Provided policy '{self.DEFAULT_POLICY_NAME}' overrides default_policy parameter. "
                    f"Using provided: {provided_default.name}"
                )
                self._default_policy = provided_default

        # Fail fast on configuration errors
        self._validate_at_startup()

    def _validate_at_startup(self) -> None:
        """Comprehensive policy validation - fail fast pattern"""
        if not self._policies:
            raise ValueError("PolicyRegistry requires at least one policy")

        for name, policy in self._policies.items():
            # Protocol compliance checks
            if not hasattr(policy, 'execute'):
                raise TypeError(f"Policy '{name}' must implement execute() method")
            if not hasattr(policy, 'name'):
                raise TypeError(f"Policy '{name}' must implement name property")

            # Runtime validation
            try:
                policy_name = policy.name
                if not policy_name:
                    raise ValueError(f"Policy '{name}' has empty name property")

                # Name consistency warning (not error - allows flexibility)
                if name != self.DEFAULT_POLICY_NAME and policy_name != name:
                    logger.warning(
                        f"Policy registered as '{name}' but reports name '{policy_name}'"
                    )

            except Exception as e:
                raise TypeError(f"Policy '{name}' name property failed: {e}") from e

    def get_policy(self, name: Optional[str], /) -> PolicyExecutor:
        """Get policy with robust fallback handling

        Args:
            name: Policy name or None for default
                  (positional-only to prevent 'None' string confusion)

        Returns:
            PolicyExecutor instance (never None)
        """
        if name is None:
            return self._default_policy

        if name not in self._policies:
            available = list(self._policies.keys())
            logger.warning(
                f"Policy '{name}' not found in registry {available}, "
                f"using {self.DEFAULT_POLICY_NAME}"
            )
            return self._default_policy

        return self._policies[name]

    def list_policies(self) -> List[str]:
        """List all available policy names for introspection"""
        return sorted(self._policies.keys())

    def has_policy(self, name: str) -> bool:
        """Check policy existence without generating warnings"""
        return name in self._policies

    # Immutable public interface
    def with_policy(self, name: str, policy: PolicyExecutor) -> 'PolicyRegistry':
        """Return new registry with additional policy (immutable pattern)"""
        new_policies = dict(self._policies)

        if name in new_policies:
            logger.warning(f"Policy '{name}' already exists, overriding")

        new_policies[name] = policy
        return PolicyRegistry(self._default_policy, new_policies)

    def with_no_retry_default(self) -> 'PolicyRegistry':
        """Convenience method: return registry with NoRetryPolicy as default

        IMPORTANT: Preserves the current default under DEFAULT_POLICY_NAME,
        even if it was previously overridden by the caller.
        """
        no_retry = NoRetryPolicy()

        # Preserve whatever is currently registered as the default policy
        current_default = self._policies.get(self.DEFAULT_POLICY_NAME, self._default_policy)

        return PolicyRegistry(
            default_policy=no_retry,
            policies={
                self.DEFAULT_POLICY_NAME: current_default,  # Preserve existing default
                "no_retry": no_retry
            }
        )
```

### **V8-4: Enhanced Operation Model**

```python
# Enhance existing OperationModel @dataclass (around line 1354)
@dataclass
class OperationModel:
    """API operation configuration with policy support"""
    name: str
    method: str
    endpoint: str
    protocol: str = "json"
    auth_required: bool = True
    retry_count: int = 3
    max_delay: Optional[float] = None      # Per-operation delay cap override
    policy_override: Optional[str] = None  # Validated policy name override

    def __post_init__(self):
        """Validate configuration at construction time"""
        if self.retry_count < 0:
            raise ValueError(f"retry_count must be >= 0, got {self.retry_count}")
        if self.max_delay is not None and self.max_delay <= 0:
            raise ValueError(f"max_delay must be > 0, got {self.max_delay}")
        if self.method.upper() not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            raise ValueError(f"Unsupported HTTP method: {self.method}")
```

## **📋 Implementation Stories**

### **Story V8-1: Error Categorization & Factory Methods**
**Duration:** 1 day
**Risk:** Low (additive pattern implementation)

**Tasks:**
1. **Add ErrorCategory enum** at line 873 (before CloudError definition)
2. **Enhance CloudError @dataclass** with category field and factory methods
3. **Create comprehensive migration script** for all 17 CloudError construction sites
4. **Update all 17 error construction sites** with proper categorization:
   - Line 1602: `_make_http_request` unsupported method → `CloudError.transport`
   - Line 1574: Network exceptions → `CloudError.transport`
   - Line 1639: HTTP 429/5xx errors → `CloudError.semantic_retryable`
   - Line 1205-1707: Authentication errors → `CloudError.semantic`
   - Lines 1264, 1276, 1338, etc.: Protocol/business logic errors → `CloudError.semantic`

**AST-Based Migration Script:**
```python
#!/usr/bin/env python3
"""AST-based CloudError factory migration script

LIMITATIONS:
- Only processes constructor calls with keyword-only arguments (no positional args)
- Constructor calls like CloudError("message", code=...) will be skipped
- This covers current codebase patterns but may miss future additions

COVERAGE:
- Handles all 17 CloudError() constructor calls in spike_architecture.py
- Provides detailed reporting of migrated vs skipped calls
- Creates backup files for safe rollback
"""

import ast
import sys
from typing import Dict, List, Tuple

class CloudErrorMigrator(ast.NodeTransformer):
    """Transform CloudError constructor calls to factory methods"""

    def __init__(self):
        self.migrations: List[Tuple[int, str, str]] = []
        self.skipped_calls: List[Tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Transform CloudError constructor calls"""
        if (isinstance(node.func, ast.Name) and
            node.func.id == 'CloudError' and
            self._is_constructor_call(node)):

            # Extract constructor arguments
            args = self._extract_args(node)
            if not args:
                self.skipped_calls.append((node.lineno, ast.unparse(node)))
                return node  # Skip if can't parse

            # Determine factory method based on context
            factory_method = self._determine_factory_method(args)
            migration = self._create_factory_call(factory_method, args)

            self.migrations.append((node.lineno,
                                  ast.unparse(node),
                                  ast.unparse(migration)))
            return migration

        return self.generic_visit(node)

    def _is_constructor_call(self, node: ast.Call) -> bool:
        """Check if this is a CloudError constructor (not method call)

        LIMITATION: Only handles keyword-only constructors.
        Calls like CloudError("msg", code=...) will be skipped.
        """
        return len(node.args) == 0 and len(node.keywords) > 0

    def _extract_args(self, node: ast.Call) -> Dict[str, ast.AST]:
        """Extract keyword arguments from constructor call"""
        args = {}
        for kw in node.keywords:
            if kw.arg:
                args[kw.arg] = kw.value
        return args

    def _determine_factory_method(self, args: Dict[str, ast.AST]) -> str:
        """Determine appropriate factory method based on error code and context"""

        # Extract error code if available
        if 'code' in args and isinstance(args['code'], ast.Attribute):
            code_name = args['code'].attr

            # Transport errors - network level
            if code_name in {'NETWORK_ERROR'}:
                return 'transport'

            # Retryable semantic errors - 5xx/429 status codes
            elif code_name in {'SERVICE_UNAVAILABLE', 'RATE_LIMITED'}:
                return 'semantic_retryable'

            # Non-retryable semantic errors - auth/business logic
            elif code_name in {'AUTHENTICATION_REQUIRED', 'INVALID_CREDENTIALS',
                              'TWO_FACTOR_REQUIRED', 'UNKNOWN'}:
                return 'semantic'

        # Default to semantic for safety
        return 'semantic'

    def _create_factory_call(self, factory_method: str, args: Dict[str, ast.AST]) -> ast.Call:
        """Create factory method call with preserved arguments"""

        # Remove retryable argument if it matches factory default
        filtered_args = dict(args)
        if 'retryable' in filtered_args:
            retryable_value = self._extract_bool_value(filtered_args['retryable'])
            factory_default = (factory_method == 'transport' or
                             factory_method == 'semantic_retryable')

            if retryable_value == factory_default:
                del filtered_args['retryable']

        # Create CloudError.factory_method() call
        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='CloudError', ctx=ast.Load()),
                attr=factory_method,
                ctx=ast.Load()
            ),
            args=[],
            keywords=[ast.keyword(arg=k, value=v) for k, v in filtered_args.items()]
        )

    def _extract_bool_value(self, node: ast.AST) -> bool:
        """Extract boolean value from AST node"""
        if isinstance(node, ast.Constant):
            return bool(node.value)
        elif isinstance(node, ast.NameConstant):  # Python < 3.8
            return bool(node.value)
        return False

def migrate_file(filename: str) -> None:
    """Migrate CloudError constructors in file"""

    with open(filename, 'r') as f:
        source = f.read()

    # Parse and transform
    tree = ast.parse(source)
    migrator = CloudErrorMigrator()
    new_tree = migrator.visit(tree)

    # Generate new source
    new_source = ast.unparse(new_tree)

    # Report migrations and limitations
    print(f"🔄 Migrated {len(migrator.migrations)} of 17 CloudError calls in {filename}")
    for lineno, old, new in migrator.migrations:
        print(f"  Line {lineno}: {old[:50]}... → {new[:50]}...")

    if migrator.skipped_calls:
        print(f"⚠️  Skipped {len(migrator.skipped_calls)} calls (manual review needed):")
        for lineno, call in migrator.skipped_calls:
            print(f"  Line {lineno}: {call[:70]}...")

    # Write backup and new file
    with open(f"{filename}.backup", 'w') as f:
        f.write(source)

    with open(filename, 'w') as f:
        f.write(new_source)

    print(f"✅ Migration complete. Backup saved as {filename}.backup")

if __name__ == "__main__":
    migrate_file("spike_architecture.py")
```

**Acceptance Criteria:**
- ✅ All 17 CloudError construction sites migrated to appropriate factory methods
- ✅ Transport vs semantic categorization accurate based on error code context
- ✅ AST-based migration preserves code structure and handles complex expressions
- ✅ Factory methods reduce constructor verbosity by 40%+
- ✅ Backwards compatibility: existing error handling unchanged

### **Story V8-2: Policy Infrastructure Implementation**
**Duration:** 1.5 days
**Risk:** Medium (Strategy pattern implementation)

**Tasks:**
1. **Implement core policy classes** (PolicyContext, PolicyExecutor, DefaultBackoffPolicy, NoRetryPolicy)
2. **Create FakeSleeper test utility** with comprehensive assertion methods
3. **Implement PolicyRegistry** with startup validation and immutable interface
4. **Enhance OperationModel** with policy configuration fields
5. **Create comprehensive contract tests** proving exact mathematical parity

**Mathematical Parity Validation:**
```python
# test_policy_mathematical_parity.py

import pytest
import random
from unittest.mock import patch
import statistics

class TestDefaultBackoffPolicyParity:
    """Comprehensive contract tests ensuring exact @backoff equivalence"""

    def test_exponential_sequence_deterministic(self, fake_sleeper):
        """Verify exact exponential progression with controlled jitter"""

        # Deterministic jitter for precise testing
        def fixed_jitter(delay: float) -> float:
            return delay * 0.6  # Always 60% of calculated delay

        policy = DefaultBackoffPolicy(
            base_delay=0.5,
            jitter_func=fixed_jitter,
            sleep_func=fake_sleeper.sleep
        )

        operation = OperationModel(
            name="test_op", method="POST", endpoint="/test", retry_count=5
        )
        ctx = PolicyContext(operation=operation, url="http://test.example.com")

        call_count = 0
        def always_fail():
            nonlocal call_count
            call_count += 1
            return Result.failure(CloudError.semantic_retryable(
                code=CloudErrorCode.SERVICE_UNAVAILABLE,
                message=f"Test failure {call_count}"
            ))

        result = policy.execute(ctx, always_fail)

        # Expected: (0.5*0.6), (1.0*0.6), (2.0*0.6), (4.0*0.6)
        expected_delays = [0.3, 0.6, 1.2, 2.4]

        assert result.is_failure
        assert call_count == 5  # Initial + 4 retries
        fake_sleeper.assert_sleep_sequence(expected_delays, tolerance=0.001)
        assert abs(fake_sleeper.total_sleep - 4.5) < 0.001

    def test_jitter_distribution_statistical_properties(self):
        """Verify backoff.full_jitter maintains uniform distribution properties"""

        samples_per_delay = 100
        delays = [0.5, 1.0, 2.0, 4.0, 8.0]

        for base_delay in delays:
            jitter_samples = [backoff.full_jitter(base_delay) for _ in range(samples_per_delay)]

            # Range constraint: 0 <= jittered <= base_delay
            assert all(0 <= sample <= base_delay for sample in jitter_samples)

            # Statistical properties of uniform distribution
            mean = statistics.mean(jitter_samples)
            expected_mean = base_delay / 2

            # Within 10% of expected mean (should be much tighter with 100 samples)
            assert abs(mean - expected_mean) < base_delay * 0.1

            # Standard deviation for uniform distribution: range/sqrt(12)
            stdev = statistics.stdev(jitter_samples)
            expected_stdev = base_delay / (12 ** 0.5)
            assert abs(stdev - expected_stdev) < expected_stdev * 0.2  # 20% tolerance

    def test_retry_decision_logic_parity(self, fake_sleeper):
        """Verify retry decisions match current _should_retry logic exactly"""

        policy = DefaultBackoffPolicy(sleep_func=fake_sleeper.sleep)

        test_cases = [
            # (retryable, attempt_no, max_tries, should_retry)
            (True, 0, 3, True),    # First retry of 3
            (True, 1, 3, True),    # Second retry of 3
            (True, 2, 3, False),   # Would be 4th attempt, exceeds max_tries=3
            (False, 0, 3, False),  # Non-retryable error
            (True, 0, 1, False),   # max_tries=1, no retries allowed
        ]

        for retryable, attempt_no, max_tries, expected_should_retry in test_cases:
            error = CloudError.semantic(
                code=CloudErrorCode.SERVICE_UNAVAILABLE,
                message="Test error",
                retryable=retryable
            )

            actual_should_retry = policy._should_retry(error, attempt_no, max_tries)
            assert actual_should_retry == expected_should_retry, \
                f"retry_decision({retryable}, {attempt_no}, {max_tries}) = {actual_should_retry}, expected {expected_should_retry}"

    def test_max_delay_cap_enforcement(self, fake_sleeper):
        """Verify max_delay capping works correctly"""

        policy = DefaultBackoffPolicy(
            base_delay=0.5,
            max_delay=2.0,  # Cap at 2 seconds
            jitter_func=lambda x: x,  # No jitter for precise testing
            sleep_func=fake_sleeper.sleep
        )

        operation = OperationModel(name="test", method="POST", endpoint="/test", retry_count=6)
        ctx = PolicyContext(operation=operation)

        def always_fail():
            return Result.failure(CloudError.semantic_retryable(
                code=CloudErrorCode.SERVICE_UNAVAILABLE,
                message="Test failure"
            ))

        policy.execute(ctx, always_fail)

        # Expected without cap: [0.5, 1.0, 2.0, 4.0, 8.0]
        # Expected with 2.0 cap: [0.5, 1.0, 2.0, 2.0, 2.0]
        expected_delays = [0.5, 1.0, 2.0, 2.0, 2.0]

        fake_sleeper.assert_sleep_sequence(expected_delays)

    def test_non_retryable_immediate_failure(self, fake_sleeper):
        """Verify non-retryable errors fail immediately without delay"""

        policy = DefaultBackoffPolicy(sleep_func=fake_sleeper.sleep)
        operation = OperationModel(name="test", method="POST", endpoint="/test", retry_count=5)
        ctx = PolicyContext(operation=operation)

        def auth_failure():
            return Result.failure(CloudError.semantic(
                code=CloudErrorCode.AUTHENTICATION_REQUIRED,
                message="Auth required",
                retryable=False
            ))

        result = policy.execute(ctx, auth_failure)

        assert result.is_failure
        assert result.error.code == CloudErrorCode.AUTHENTICATION_REQUIRED
        fake_sleeper.assert_no_sleeps()
        assert ctx.attempt_no == 0  # Single attempt only

class TestNoRetryPolicy:
    """Verify NoRetryPolicy deterministic behavior"""

    def test_single_attempt_no_sleep(self, fake_sleeper):
        """Verify NoRetryPolicy executes exactly once"""

        policy = NoRetryPolicy()
        operation = OperationModel(name="test", method="POST", endpoint="/test", retry_count=10)
        ctx = PolicyContext(operation=operation)

        call_count = 0
        def counting_failure():
            nonlocal call_count
            call_count += 1
            return Result.failure(CloudError.semantic_retryable(
                code=CloudErrorCode.SERVICE_UNAVAILABLE,
                message="Test failure"
            ))

        result = policy.execute(ctx, counting_failure)

        assert result.is_failure
        assert call_count == 1
        assert ctx.attempt_no == 0
        fake_sleeper.assert_no_sleeps()

    def test_success_on_first_attempt(self):
        """Verify NoRetryPolicy returns success immediately"""

        policy = NoRetryPolicy()
        operation = OperationModel(name="test", method="POST", endpoint="/test")
        ctx = PolicyContext(operation=operation)

        def immediate_success():
            return Result.success(b"test response")

        result = policy.execute(ctx, immediate_success)

        assert result.is_success
        assert result.value == b"test response"
        assert ctx.attempt_no == 0
```

**Acceptance Criteria:**
- ✅ DefaultBackoffPolicy produces identical mathematical sequences to current @backoff
- ✅ Contract tests verify behavior with deterministic and statistical jitter validation
- ✅ NoRetryPolicy enables deterministic testing with zero sleeps
- ✅ PolicyRegistry validates all configurations at startup time
- ✅ FakeSleeper provides comprehensive test assertion capabilities

### **Story V8-3: CloudClient Integration**
**Duration:** 1 day
**Risk:** Medium (dependency injection implementation)

**Tasks:**
1. **Extract `_single_attempt` method** from `_execute_http_request` (lines 1524-1582)
2. **Replace retry logic** with PolicyExecutor delegation
3. **Remove nested allocations** (`_Retryable` class and `_run` function)
4. **Update CloudClient constructor** to accept PolicyExecutor parameter
5. **Add PolicyContext population** with comprehensive execution state

**Critical Implementation:**
```python
# Update CloudClient class (line 1391)

class CloudClient:
    """Generic client with injected policy execution"""

    def __init__(self,
                 service_model: ServiceModel,
                 auth_provider: AuthenticationProvider,
                 protocol_handlers: Dict[str, ProtocolHandler],
                 event_bus: EventBus,
                 policy_executor: PolicyExecutor):  # ← NEW: Injected policy
        self.service_model = service_model
        self.auth_provider = auth_provider
        self.protocol_handlers = protocol_handlers
        self.event_bus = event_bus
        self.policy_executor = policy_executor  # ← NEW: Store injected policy

        # Request logging setup (unchanged)
        param_logger = ParameterLogger(ParameterRedactionStrategy())
        self.request_logger = RequestLogger(param_logger)

    def _execute_http_request(self,
                              session: Any,
                              operation: OperationModel,
                              url: str,
                              headers: Dict[str, str],
                              params: Dict[str, Any],
                              request_data: bytes) -> Result[bytes, CloudError]:
        """Simplified delegation to policy executor - no more per-call allocation!"""

        # Create execution context
        ctx = PolicyContext(
            operation=operation,
            url=url,  # For policy logging and debugging
            attempt_no=0,  # Will be updated by policy
            last_error=None
        )

        # Delegate to injected policy - eliminates nested function allocation
        return self.policy_executor.execute(ctx, lambda: self._single_attempt(
            session, operation, url, headers, params, request_data
        ))

    def _single_attempt(self,
                       session: Any,
                       operation: OperationModel,
                       url: str,
                       headers: Dict[str, str],
                       params: Dict[str, Any],
                       request_data: bytes) -> Result[bytes, CloudError]:
        """Execute single HTTP attempt with preserved error categorization logic

        CRITICAL: This method extracts the exact logic from the current _run() function
        while preserving error categorization and retryable flag behavior.
        """

        # 1. Transport layer - network/connection issues
        transport_result = self._make_http_request(
            session, operation, url, headers, params, request_data
        )
        if transport_result.is_failure:
            # Transport errors already properly categorized with retryable flags
            return transport_result

        # 2. Semantic layer - HTTP status code interpretation
        semantic_result = self._handle_response(transport_result.value)
        # Semantic errors already properly categorized with retryable flags
        return semantic_result

    def _make_http_request(self,
                          session: Any,
                          operation: OperationModel,
                          url: str,
                          headers: Dict[str, str],
                          params: Dict[str, Any],
                          request_data: bytes) -> Result[Any, CloudError]:
        """HTTP request execution with transport error categorization

        Updates line 1611+ to use factory methods and proper categorization.
        """
        method = operation.method.upper()

        try:
            if method == "POST":
                response = session.post(url, data=request_data, headers=headers, params=params)
            elif method == "GET":
                response = session.get(url, headers=headers, params=params)
            else:
                # UPDATED: Use transport factory for unsupported methods
                return Result.failure(
                    CloudError.transport(
                        code=CloudErrorCode.UNKNOWN,
                        message=f"Unsupported HTTP method: {operation.method}",
                        details={"method": operation.method},
                        retryable=False  # Don't retry configuration errors
                    )
                )
            return Result.success(response)

        except requests.RequestException as e:
            # UPDATED: Network failures are transport errors, typically retryable
            return Result.failure(
                CloudError.transport(
                    code=CloudErrorCode.NETWORK_ERROR,
                    message=f"Network request failed: {str(e)}",
                    details={"url": url, "exception": repr(e)},
                    retryable=True  # Network issues should be retried
                )
            )

    def _handle_response(self, response: Any) -> Result[bytes, CloudError]:
        """HTTP response handling with semantic error categorization

        Updates line 1639+ to use factory methods and proper categorization.
        """
        response_logger.log_response_safely(response, "API response")

        if response.ok:
            logger.info("✅ %s bytes received", len(response.content))
            return Result.success(response.content)

        # ── failure path with semantic categorization ──────────────────
        error_details = {
            "status_code": response.status_code,
            "response_text": response.text,
        }
        try:
            error_details["error_json"] = response.json()
        except json.JSONDecodeError:
            pass

        # UPDATED: Use semantic factories with proper retryable logic
        if response.status_code == 429:
            # Rate limiting - semantic but retryable
            return Result.failure(
                CloudError.semantic_retryable(
                    code=CloudErrorCode.RATE_LIMITED,
                    message=f"Rate limited: {response.reason}",
                    details=error_details
                )
            )
        elif 500 <= response.status_code < 600:
            # Server errors - semantic but retryable
            return Result.failure(
                CloudError.semantic_retryable(
                    code=CloudErrorCode.SERVICE_UNAVAILABLE,
                    message=f"Server error: {response.status_code} {response.reason}",
                    details=error_details
                )
            )
        else:
            # Client errors (4xx) - semantic and non-retryable
            return Result.failure(
                CloudError.semantic(
                    code=CloudErrorCode.INVALID_CREDENTIALS if response.status_code == 401
                         else CloudErrorCode.UNKNOWN,
                    message=f"Client error: {response.status_code} {response.reason}",
                    details=error_details,
                    retryable=False
                )
            )
```



**Acceptance Criteria:**
- ✅ `_execute_http_request` becomes <15 lines, pure delegation to policy
- ✅ `_single_attempt` preserves exact current error handling logic
- ✅ Memory profiling shows 70%+ reduction in retry path allocations
- ✅ No behavioral changes in error categorization or retry decisions
- ✅ Policy injection enables complete testing control

### **Story V8-4: CloudSession Policy Integration**
**Duration:** 1 day
**Risk:** Low (high-level spike integration)

**Tasks:**
1. **Update CloudSession constructor** to accept optional PolicyRegistry
2. **Modify client creation** to inject PolicyExecutor into CloudClient
3. **Add policy validation** for operation-level overrides
4. **Implement session helper methods** for testing and extension
5. **Update service model loading** with policy configuration support

**CloudSession Enhancement:**
```python
# Update CloudSession class (line 1698)

class CloudSession:
    """User-facing session with comprehensive policy injection support"""

    def __init__(self,
                 policy_registry: Optional[PolicyRegistry] = None):
        """Initialize session with configurable policy system

        Args:
            policy_registry: Custom policy configuration (defaults to production setup)
        """
        self.event_bus = EventBus()
        self.protocol_handlers: Dict[str, ProtocolHandler] = {
            "json": JsonProtocolHandler(),
        }
        self._clients: Dict[str, CloudClient] = {}
        self._auth_provider: Optional[AuthenticationProvider] = None

        # Default spike policy configuration
        if policy_registry is None:
            default_policy = DefaultBackoffPolicy()
            self.policy_registry = PolicyRegistry(
                default_policy=default_policy,
                policies={
                    PolicyRegistry.DEFAULT_POLICY_NAME: default_policy,
                    "no_retry": NoRetryPolicy()
                }
            )
        else:
            self.policy_registry = policy_registry

        # Log policy system status for spike demonstration
        logger.info("✅ CloudSession initialized with policies: %s",
                   self.policy_registry.list_policies())

    def client(self,
               service_name: str,
               policy_override: Optional[str] = None) -> Result[CloudClient, CloudError]:
        """Get service client with optional policy override

        Args:
            service_name: Service identifier (e.g., "apple-device-management")
            policy_override: Override policy for this client instance

        Returns:
            Result containing CloudClient with injected policy executor
        """
        if not self._auth_provider:
            return Result.failure(
                CloudError.semantic(
                    code=CloudErrorCode.AUTHENTICATION_REQUIRED,
                    message="Session not authenticated - call authenticate() first",
                    details={"service": service_name}
                )
            )

        # Client caching with policy-aware cache keys
        cache_key = f"{service_name}:{policy_override or PolicyRegistry.DEFAULT_POLICY_NAME}"
        if cache_key in self._clients:
            logger.debug("♻️  Using cached client for %s", cache_key)
            return Result.success(self._clients[cache_key])

        # Service model loading and validation
        service_model = self._load_service_model(service_name)
        if not service_model:
            return Result.failure(
                CloudError.semantic(
                    code=CloudErrorCode.SERVICE_UNAVAILABLE,
                    message=f"Service model not available: {service_name}",
                    details={
                        "service": service_name,
                        "available_services": ["apple-device-management"]  # Known services
                    }
                )
            )

        # Policy resolution with validation
        policy_name = policy_override or PolicyRegistry.DEFAULT_POLICY_NAME
        if not self.policy_registry.has_policy(policy_name):
            return Result.failure(
                CloudError.semantic(
                    code=CloudErrorCode.UNKNOWN,
                    message=f"Policy not found: {policy_name}",
                    details={
                        "requested_policy": policy_name,
                        "available_policies": self.policy_registry.list_policies()
                    }
                )
            )

        policy_executor = self.policy_registry.get_policy(policy_name)
        logger.debug("🔧 Using policy '%s' for client %s", policy_executor.name, service_name)

        # Client creation with policy injection
        client = CloudClient(
            service_model=service_model,
            auth_provider=self._auth_provider,
            protocol_handlers=self.protocol_handlers,
            event_bus=self.event_bus,
            policy_executor=policy_executor  # ← KEY: Policy injection point
        )

        self._clients[cache_key] = client
        return Result.success(client)

    def with_no_retry(self) -> 'CloudSession':
        """Create testing session with NoRetryPolicy as default

        Returns:
            New CloudSession configured for deterministic offline testing
        """
        no_retry_registry = self.policy_registry.with_no_retry_default()
        new_session = CloudSession(policy_registry=no_retry_registry)
        new_session._auth_provider = self._auth_provider  # Preserve auth state
        return new_session

    def with_policy(self, name: str, policy: PolicyExecutor) -> 'CloudSession':
        """Create session with additional policy

        Args:
            name: Policy identifier for registration
            policy: PolicyExecutor implementation

        Returns:
            New CloudSession with additional policy available
        """
        new_registry = self.policy_registry.with_policy(name, policy)
        new_session = CloudSession(policy_registry=new_registry)
        new_session._auth_provider = self._auth_provider  # Preserve auth state
        return new_session

    def with_fast_retry(self, base_delay: float = 0.001) -> 'CloudSession':
        """Create session with fast retry policy for integration testing

        Args:
            base_delay: Minimal delay for fast testing (default: 1ms)

        Returns:
            New CloudSession with fast retry policy as default
        """
        fast_policy = DefaultBackoffPolicy(base_delay=base_delay)

        # Preserve whatever is currently the canonical default policy
        current_default = self.policy_registry.get_policy(PolicyRegistry.DEFAULT_POLICY_NAME)

        fast_registry = PolicyRegistry(
            default_policy=fast_policy,
            policies={
                "fast_retry": fast_policy,
                PolicyRegistry.DEFAULT_POLICY_NAME: current_default,  # Preserve existing
                "no_retry": NoRetryPolicy()
            }
        )
        new_session = CloudSession(policy_registry=fast_registry)
        new_session._auth_provider = self._auth_provider
        return new_session

    def _load_service_model(self, service_name: str) -> Optional[ServiceModel]:
        """Load service model with enhanced policy configuration support

        Updates existing logic (line 1766+) to support policy overrides.
        """
        if service_name == "apple-device-management":
            if (self._auth_provider and
                hasattr(self._auth_provider, "get_session_data") and
                self._auth_provider.get_session_data().get("webservices")):

                webservices = self._auth_provider.get_session_data()["webservices"]
                if "findme" in webservices:
                    findme_url = webservices["findme"]["url"]
                    logger.info("🌐 Using Find My iPhone service URL: %s", findme_url)

                    return ServiceModel(
                        name="apple-device-management",
                        base_url=findme_url,
                        operations={
                            "locate_device": OperationModel(
                                name="locate_device",
                                method="POST",
                                endpoint=FMI_REFRESH_CLIENT_PATH,
                                protocol="json",
                                retry_count=3,  # Default retry behavior
                                max_delay=30.0,  # Cap delays for device operations
                            ),
                            "play_sound": OperationModel(
                                name="play_sound",
                                method="POST",
                                endpoint=FMI_PLAY_SOUND_PATH,
                                protocol="json",
                                retry_count=2,  # Fewer retries for sound operations
                                max_delay=10.0,
                            ),
                        },
                    )

                logger.warning("❌ Find My iPhone service not available in webservices")
                return None

            logger.warning("❌ No webservices available - authentication incomplete")
            return None

        logger.warning("❌ Unknown service: %s", service_name)
        return None
```

**Acceptance Criteria:**
- ✅ Session-level policy configuration with validation
- ✅ Operation-level policy overrides validated at client creation
- ✅ Helper methods enable seamless test setup (`with_no_retry`, `with_fast_retry`)
- ✅ Policy-aware client caching prevents redundant instantiation
- ✅ Enhanced service model loading supports operation-specific policy configuration

### **Story V8-5: Test Infrastructure & Validation**
**Duration:** 1.5 days
**Risk:** Low (pattern validation and testing)

**Tasks:**
1. **Create comprehensive test utilities** and fixtures
2. **Implement contract tests** proving exact behavioral parity
3. **Add performance benchmarks** measuring allocation reduction
4. **Create migration validation suite** ensuring zero behavioral drift
5. **Document testing patterns** for future policy development

**Test Infrastructure:**
```python
# tests/test_policy_infrastructure.py

import pytest
import time
import tracemalloc
import statistics
from unittest.mock import patch, MagicMock
from typing import List, Tuple

@pytest.fixture(scope="function")
def fake_sleeper():
    """Function-scoped FakeSleeper to prevent cross-test contamination"""
    sleeper = FakeSleeper()
    yield sleeper
    sleeper.reset()

@pytest.fixture(scope="function")
def no_retry_session():
    """Session configured for deterministic testing with zero sleeps"""
    return CloudSession().with_no_retry()

@pytest.fixture(scope="function")
def fast_retry_session():
    """Session with very fast retries for integration testing"""
    return CloudSession().with_fast_retry(base_delay=0.001)

@pytest.fixture(scope="function")
def mock_auth_provider():
    """Fully mocked authentication provider for testing"""
    mock_auth = MagicMock(spec=AuthenticationProvider)
    mock_auth.get_session_data.return_value = {
        "webservices": {"findme": {"url": "http://mock.example.com"}},
        "account_info": {"dsInfo": {"dsid": "test_dsid"}}
    }
    mock_auth.get_session.return_value = MagicMock(spec=requests.Session)
    mock_auth.get_auth_context.return_value = Result.success(AuthContext(
        session_token="mock_token",
        auth_headers={"Authorization": "Bearer mock_token"}
    ))
    return mock_auth

class TestBehavioralParity:
    """Comprehensive validation of exact behavioral equivalence"""

    def test_complete_retry_flow_parity(self, fake_sleeper):
        """End-to-end test proving mathematical equivalence to current implementation"""

        # Create policy with controlled jitter for deterministic testing
        def predictable_jitter(delay: float) -> float:
            return delay * 0.8  # 80% of calculated delay

        policy = DefaultBackoffPolicy(
            base_delay=0.5,
            max_delay=10.0,
            jitter_func=predictable_jitter,
            sleep_func=fake_sleeper.sleep
        )

        operation = OperationModel(
            name="test_operation",
            method="POST",
            endpoint="/test",
            retry_count=4
        )
        ctx = PolicyContext(operation=operation, url="http://test.example.com")

        # Simulate current @backoff behavior: fail 4 times, succeed on 5th
        call_count = 0
        def mostly_failing_attempt():
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                return Result.failure(CloudError.semantic_retryable(
                    code=CloudErrorCode.SERVICE_UNAVAILABLE,
                    message=f"Simulated failure {call_count}"
                ))
            return Result.success(b"success response")

        result = policy.execute(ctx, mostly_failing_attempt)

        # Verify success and call pattern
        assert result.is_success
        assert result.value == b"success response"
        assert call_count == 5

        # Expected delays: [0.5*0.8, 1.0*0.8, 2.0*0.8, 4.0*0.8] = [0.4, 0.8, 1.6, 3.2]
        expected_delays = [0.4, 0.8, 1.6, 3.2]
        fake_sleeper.assert_sleep_sequence(expected_delays, tolerance=0.001)
        assert abs(fake_sleeper.total_sleep - 4.5) < 0.001

    def test_max_tries_boundary_conditions(self, fake_sleeper):
        """Test edge cases around retry count boundaries"""

        policy = DefaultBackoffPolicy(sleep_func=fake_sleeper.sleep)

        test_cases = [
            (0, 0),  # retry_count=0 → max_tries=1 → no retries
            (1, 1),  # retry_count=1 → max_tries=1 → no retries
            (2, 1),  # retry_count=2 → max_tries=2 → 1 retry
            (3, 2),  # retry_count=3 → max_tries=3 → 2 retries
        ]

        for retry_count, expected_sleep_calls in test_cases:
            fake_sleeper.reset()

            operation = OperationModel(
                name="boundary_test",
                method="POST",
                endpoint="/test",
                retry_count=retry_count
            )
            ctx = PolicyContext(operation=operation)

            def always_fail():
                return Result.failure(CloudError.semantic_retryable(
                    code=CloudErrorCode.SERVICE_UNAVAILABLE,
                    message="Test failure"
                ))

            result = policy.execute(ctx, always_fail)

            assert result.is_failure
            assert fake_sleeper.call_count == expected_sleep_calls, \
                f"retry_count={retry_count} should result in {expected_sleep_calls} sleeps, got {fake_sleeper.call_count}"

class TestPerformanceBenchmarks:
    """Performance regression tests and allocation measurement"""

    def test_allocation_reduction_measurement(self):
        """Measure and verify significant allocation reduction"""

        # Simulate current approach with per-call nested function allocation
        def current_approach_simulation():
            class _Retryable(Exception):
                def __init__(self, ce):
                    super().__init__(ce.message)
                    self.ce = ce

            def _run():
                return "result"

            # Simulate the allocation pattern
            return _run()

        # New approach using method references
        policy = DefaultBackoffPolicy()
        operation = OperationModel(name="perf_test", method="POST", endpoint="/test")
        ctx = PolicyContext(operation=operation)

        def new_approach_simulation():
            return policy.execute(ctx, lambda: Result.success(b"test"))

        # Measure allocations over multiple iterations
        iterations = 1000

        # Current approach measurement
        tracemalloc.start()
        for _ in range(iterations):
            current_approach_simulation()
        current_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        # New approach measurement
        tracemalloc.start()
        for _ in range(iterations):
            new_approach_simulation()
        new_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        # Calculate reduction and verify target
        if current_memory > 0:
            reduction_percentage = ((current_memory - new_memory) / current_memory) * 100
            logger.info(f"📊 Memory allocation reduction: {reduction_percentage:.1f}%")

            # Verify 70%+ reduction target
            assert reduction_percentage >= 70.0, \
                f"Expected ≥70% allocation reduction, achieved {reduction_percentage:.1f}%"
        else:
            logger.warning("⚠️  Could not measure current approach allocations")

    def test_policy_execution_overhead(self, fake_sleeper):
        """Measure policy execution overhead vs direct method calls"""

        policy = NoRetryPolicy()  # Minimal overhead policy
        operation = OperationModel(name="overhead_test", method="POST", endpoint="/test")
        ctx = PolicyContext(operation=operation)

        def simple_success():
            return Result.success(b"test response")

        # Measure direct call
        start_time = time.perf_counter()
        for _ in range(1000):
            simple_success()
        direct_time = time.perf_counter() - start_time

        # Measure policy-wrapped call with fresh context each time
        start_time = time.perf_counter()
        for _ in range(1000):
            # Create fresh context for each call (realistic usage pattern)
            fresh_ctx = PolicyContext(operation=operation)
            policy.execute(fresh_ctx, simple_success)
        policy_time = time.perf_counter() - start_time

        overhead_percentage = ((policy_time - direct_time) / direct_time) * 100
        logger.info(f"📊 Policy execution overhead: {overhead_percentage:.1f}%")

        # Verify overhead is reasonable (<10% aligned with success metrics)
        assert overhead_percentage < 10.0, \
            f"Policy overhead too high: {overhead_percentage:.1f}% (target: <10%)"

class TestOfflineIntegration:
    """End-to-end offline testing capabilities"""

    def test_complete_offline_device_location(self, no_retry_session, mock_auth_provider):
        """Test entire device location flow offline with zero sleeps"""

        # Setup session with mock auth
        no_retry_session._auth_provider = mock_auth_provider

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"content": [], "statusCode": "200"}'
        mock_response.status_code = 200

        # Configure mock session to return mock response
        mock_session = mock_auth_provider.get_session.return_value
        mock_session.post.return_value = mock_response

        # Get client and execute operation
        client_result = no_retry_session.client("apple-device-management")
        assert client_result.is_success

        client = client_result.value
        assert isinstance(client.policy_executor, NoRetryPolicy)

        # Execute device location with mocked components
        start_time = time.time()
        result = client.invoke_operation("locate_device", {})
        execution_time = time.time() - start_time

        # Verify offline execution
        assert result.is_success
        assert execution_time < 0.1, f"Expected <0.1s execution, got {execution_time:.3f}s"

        # Verify mock calls
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/fmipservice/client/web/refreshClient" in call_args[1]["url"] or \
               call_args[0][0].endswith("/fmipservice/client/web/refreshClient")

    def test_policy_switching_runtime(self, fast_retry_session, mock_auth_provider):
        """Test runtime policy switching capabilities"""

        fast_retry_session._auth_provider = mock_auth_provider

        # Get clients with different policies
        default_client_result = fast_retry_session.client("apple-device-management")
        no_retry_client_result = fast_retry_session.client("apple-device-management", "no_retry")

        assert default_client_result.is_success
        assert no_retry_client_result.is_success

        default_client = default_client_result.value
        no_retry_client = no_retry_client_result.value

        # Verify different policy executors
        assert isinstance(default_client.policy_executor, DefaultBackoffPolicy)
        assert isinstance(no_retry_client.policy_executor, NoRetryPolicy)
        assert default_client.policy_executor.name == "fast_retry"
        assert no_retry_client.policy_executor.name == "no_retry"

        # Verify they're different client instances (policy-aware caching)
        assert default_client is not no_retry_client

class TestPolicyRegistryValidation:
    """Test startup validation and error handling"""

    def test_invalid_policy_registration(self):
        """Test registry validation catches configuration errors"""

        # Policy missing execute method
        class InvalidPolicy:
            @property
            def name(self):
                return "invalid"

        with pytest.raises(TypeError, match="must implement execute"):
            PolicyRegistry(
                default_policy=DefaultBackoffPolicy(),
                policies={"invalid": InvalidPolicy()}
            )

    def test_duplicate_policy_warning(self, caplog):
        """Test duplicate policy registration generates warnings"""

        default_policy = DefaultBackoffPolicy()
        duplicate_policy = NoRetryPolicy()

        registry = PolicyRegistry(
            default_policy=default_policy,
            policies={PolicyRegistry.DEFAULT_POLICY_NAME: duplicate_policy}
        )

        # Should use provided policy and log warning
        assert "overrides default_policy parameter" in caplog.text
        assert registry.get_policy(None) == duplicate_policy

    def test_policy_name_mismatch_warning(self, caplog):
        """Test policy name mismatch generates warnings"""

        class MismatchedPolicy(PolicyExecutor):
            @property
            def name(self):
                return "different_name"

            def execute(self, ctx, attempt):
                return attempt()

        PolicyRegistry(
            default_policy=DefaultBackoffPolicy(),
            policies={"registered_name": MismatchedPolicy()}
        )

        assert "reports name 'different_name'" in caplog.text

# Performance benchmarking utilities
class PerformanceProfiler:
    """Utility for comprehensive performance analysis"""

    @staticmethod
    def profile_retry_path(iterations: int = 1000) -> Tuple[float, float, float]:
        """Profile retry path performance

        Returns:
            Tuple of (current_approach_time, new_approach_time, improvement_percentage)
        """
        # Simulate current approach timing
        start = time.perf_counter()
        for _ in range(iterations):
            # Simulate class and function allocation overhead
            class _Retryable(Exception):
                pass
            def _run():
                return "result"
            _run()
        current_time = time.perf_counter() - start

        # Measure new approach timing
        policy = DefaultBackoffPolicy()
        operation = OperationModel(name="perf", method="POST", endpoint="/test")
        ctx = PolicyContext(operation=operation)

        start = time.perf_counter()
        for _ in range(iterations):
            policy.execute(ctx, lambda: Result.success(b"test"))
        new_time = time.perf_counter() - start

        improvement = ((current_time - new_time) / current_time) * 100
        return current_time, new_time, improvement
```

**Test Documentation:**
```python
"""
Policy Testing Patterns and Guidelines
=====================================

OFFLINE TESTING:
- Use `no_retry_session` fixture for deterministic, zero-sleep testing
- Mock AuthenticationProvider with `mock_auth_provider` fixture
- Verify operations complete in <0.1s for true offline execution

RETRY BEHAVIOR TESTING:
- Use `FakeSleeper` to capture and validate sleep patterns
- Test with deterministic jitter for precise mathematical verification
- Use statistical jitter testing for distribution property validation

PERFORMANCE TESTING:
- Use `tracemalloc` for allocation measurement
- Target 70%+ reduction in retry path allocations
- Measure policy execution overhead vs direct calls

POLICY DEVELOPMENT:
- Inherit from `PolicyExecutor` Protocol
- Implement `execute(ctx, attempt)` and `name` property
- Use `@abstractmethod` decorators for IDE support (redundant with Protocol but helpful)
- Ensure thread safety (stateless design or proper synchronization)

INTEGRATION TESTING:
- Use `fast_retry_session` for faster integration tests
- Test policy switching with same service/different policies
- Verify client caching works correctly with policy overrides

THREAD SAFETY GUIDELINES:

THREAD-SAFE SPIKE COMPONENTS:
- PolicyRegistry: Immutable after construction
- DefaultBackoffPolicy/NoRetryPolicy: Stateless design
- CloudError: Immutable dataclass
- PolicyContext: Single-use per execution

PATTERN IMPLEMENTATION NOTES:
- Policies should be stateless for Strategy pattern purity
- PolicyContext created fresh for each operation
- Dependency injection enables clean testability
- Immutable patterns prevent configuration errors
"""
```

**Acceptance Criteria:**
- ✅ All tests run offline with zero network calls and zero sleeps (NoRetryPolicy)
- ✅ Contract tests prove exact mathematical equivalence to current @backoff behavior
- ✅ Performance benchmarks demonstrate 70%+ allocation reduction
- ✅ Comprehensive test utilities support easy policy development and debugging
- ✅ Migration validation ensures zero behavioral drift from current implementation

## **🔧 Pattern Validation Strategy**

### **Strategy Pattern Implementation Validation:**
1. **Interface Compliance**: Verify PolicyExecutor protocol properly abstracts retry behavior
2. **Behavioral Equivalence**: Contract tests prove mathematical parity with current @backoff
3. **Dependency Injection**: Validate clean separation between CloudClient and retry concerns
4. **Extensibility**: Demonstrate easy addition of new policies (NoRetryPolicy, custom policies)

### **Mathematical Parity Validation:**
```python
# Contract testing approach to prove behavioral equivalence
def test_strategy_pattern_equivalence():
    """Prove DefaultBackoffPolicy === current @backoff implementation"""

    # Test identical retry sequences with deterministic jitter
    fake_sleeper = FakeSleeper()
    policy = DefaultBackoffPolicy(sleep_func=fake_sleeper.sleep)

    # Simulate identical failure patterns as current implementation
    # Verify exact delay sequences, retry counts, error handling
    # Validate jitter distribution properties statistically

def test_spike_preservation():
    """Ensure spike's Apple API demonstrations still work"""

    # Test that CloudSession.authenticate() still works
    # Test that real Apple API calls still function
    # Verify Pydantic response validation unchanged
    # Confirm logging and event systems operational
```

### **Interface Stability Validation:**
```python
# Ensure spike's existing interface remains unchanged
def test_interface_preservation():
    """Verify public API unchanged for future sprints"""

    session = CloudSession()  # Should work identically
    session.authenticate("user", "pass")  # No signature changes
    client = session.client("apple-device-management")  # Same interface
    result = client.invoke_operation("locate_device", {})  # Unchanged
```

## **📈 Pattern Demonstration Success Criteria**

### **Strategy Pattern Implementation:**
- **Clean Interface Abstraction**: PolicyExecutor protocol successfully extracts retry concerns
- **Multiple Concrete Strategies**: DefaultBackoffPolicy and NoRetryPolicy demonstrate extensibility
- **Context Independence**: CloudClient delegates retry decisions without coupling to specific policies
- **Strategy Swapping**: Runtime policy selection through dependency injection

### **Mathematical Behavioral Equivalence:**
- **Exact Retry Sequences**: Contract tests prove identical exponential backoff progression
- **Jitter Distribution**: Statistical validation of uniform random jitter properties
- **Error Categorization**: Identical retryable/non-retryable decision logic preserved
- **Performance Improvement**: 70%+ reduction in per-call memory allocations

### **Spike Interface Preservation:**
- **Apple API Integration**: Spike's real authentication and device calls continue working
- **Pydantic Validation**: Response parsing and error handling unchanged
- **Event System**: Before/after operation events still function properly
- **Logging System**: Structured logging with redaction strategies operational

### **Testing Capability Enhancement:**
- **Zero-Sleep Testing**: NoRetryPolicy enables deterministic test execution
- **Offline Testing**: Complete test isolation without network dependencies
- **Pattern Validation**: Easy verification of Strategy pattern implementation
- **Future Sprint Readiness**: Stable interfaces for continued SOLID refactoring

## **📅 Timeline & Dependencies**

| Story | Duration | Focus | Risk Level | Validation |
|-------|----------|-------|------------|------------|
| V8-1: Error Factories | 1 day | Factory Method pattern | Low | 17 sites migrated |
| V8-2: Policy Infrastructure | 1.5 days | Strategy pattern core | Medium | Mathematical parity |
| V8-3: CloudClient Integration | 1 day | Dependency injection | Medium | Performance measurement |
| V8-4: CloudSession Integration | 1 day | Pattern orchestration | Low | Interface preservation |
| V8-5: Test Infrastructure | 1.5 days | Validation framework | Low | Zero-sleep testing |

**Total: 6 days** (focused on GoF pattern implementation)
**Critical Path**: V8-1 → V8-2 → V8-3 → V8-4 → V8-5
**Focus**: Strategy pattern extraction with mathematical behavioral parity

## **🎯 Definition of Done**

### **Strategy Pattern Implementation:**
- ✅ PolicyExecutor protocol cleanly abstracts retry behavior from CloudClient
- ✅ DefaultBackoffPolicy replicates exact @backoff mathematical behavior
- ✅ NoRetryPolicy enables deterministic zero-sleep testing
- ✅ PolicyRegistry manages strategy selection via dependency injection
- ✅ CloudClient delegates retry decisions without coupling to concrete policies

### **Factory Method Pattern Implementation:**
- ✅ CloudError factory methods (transport/semantic/semantic_retryable) implemented
- ✅ All 17 CloudError constructor sites migrated to appropriate factories
- ✅ Error categorization provides clear transport vs semantic distinction
- ✅ Factory methods reduce construction verbosity and improve clarity

### **Spike Interface Preservation:**
- ✅ CloudSession/CloudClient public APIs unchanged for future sprints
- ✅ Spike's Apple API authentication and device operations continue working
- ✅ Pydantic response validation and event systems remain operational
- ✅ Structured logging and redaction strategies unchanged

### **Behavioral Parity Validation:**
- ✅ Contract tests prove mathematical equivalence to current @backoff
- ✅ Statistical validation of jitter distribution properties
- ✅ Identical error categorization and retry decision logic
- ✅ Performance benchmarks demonstrate 70%+ allocation reduction
- ✅ Zero-sleep deterministic testing capability achieved

---

**This Sprint #1 plan focuses specifically on extracting retry logic using the Strategy pattern while preserving spike functionality and interfaces. The implementation demonstrates GoF patterns and dependency injection within the spike architecture, preparing for future sprints that will continue SOLID compliance refactoring. Ready for immediate pattern implementation.**
