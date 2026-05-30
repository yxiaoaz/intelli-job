from enum import Enum


class RecruitmentType(Enum):
    """招聘类型枚举"""
    INTERN = "实习 | internship"
    GRADUATE = "校招 | graduate job"
    EXPERIENCED = "社招 | experienced or senior level"


class AcademicQualification(Enum):
    """学历要求枚举"""
    ALL = "不限"
    ASSOCIATE = "专科"
    UNDERGRADUATE = "本科"
    MASTERS = "硕士"
    DOCTOR = "博士"


class JobSource(Enum):
    """职位来源枚举"""
    ZHILIAN = "Zhilian | 智联招聘"
    SHIXISENG = "Shixiseng | 实习僧"
    WELCOME_TO_THE_JUNGLE = "Welcome to the Jungle"
    CT_GOOD_JOBS_HK = 'CT Good Jobs HK'


class ApplicationStatus(Enum):
    """申请状态枚举"""
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
