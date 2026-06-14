from app.models.base import Base
from app.models.structure import Keyword, Platform, Project, TestSuite
from app.models.user import (
    Assignment,
    Permission,
    Role,
    RolePermission,
    User,
    UserPlanRole,
    UserProjectRole,
)
from app.models.testcase import (
    TestCase,
    TestCaseRelation,
    TestCaseScriptLink,
    TestCaseVersion,
    TestStep,
)
from app.models.plan import (
    Build,
    Milestone,
    RiskAssessment,
    TestPlan,
    TestPlanCase,
    TestPlanPlatform,
)
from app.models.execution import Execution, ExecutionBug, ExecutionStep
from app.models.evidence import (
    AuditReport,
    ClaimVerification,
    ExecutionArtifact,
    ExecutionClaim,
    ExecutionReasoning,
)
from app.models.requirement import (
    ReqCoverage,
    ReqRelation,
    ReqSpec,
    ReqVersion,
    Requirement,
)
from app.models.meta import (
    Attachment,
    AuditEvent,
    CodeTracker,
    CustomField,
    CustomFieldValue,
    Inventory,
    IssueTracker,
    Plugin,
    ProjectIntegration,
    ReqMgrSystem,
    TestCaseKeyword,
    TextTemplate,
)

__all__ = ["Base"]  # plus all models above, registered on Base.metadata
