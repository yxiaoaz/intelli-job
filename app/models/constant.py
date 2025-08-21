from enum import Enum


class CompanyType(Enum):
    STATE = "state | 国企"
    PRIVATE = "private | 私企"
    FOREIGN = "foreign | 外企"


class Industry(Enum):
    pass


class RecruitmentType(Enum):
    INTERN = "实习 | internship"
    GRADUATE = "校招 | graduate job"
    EXPERIENCED = "社招 | experienced or senior level"


class AcademicQualification(Enum):
    ALL = "不限"
    ASSOCIATE = "专科"
    UNDERGRADUATE = "本科"
    MASTERS = "硕士"
    DOCTOR = "博士"


class JobSource(Enum):
    ZHILIAN = "Zhilian | 智联招聘"
    SHIXISENG = "Shixiseng | 实习僧"
    WELCOME_TO_THE_JUNGLE = "Welcome to the Jungle"
