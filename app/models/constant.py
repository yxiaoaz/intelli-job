from enum import Enum


class CompanyType(Enum):
    STATE = "state | 国企"
    PRIVATE = "private | 私企"
    FOREIGN = "foreign | 外企"

class Industry(Enum):
    pass


class PositionType(Enum):
    INTERN = "intern | 实习"
    GRADUATE = "graduate | 校招"
    EXPERIENCED = "experienced | 社招"

class JobSource(Enum):
    ZHILIAN = "Zhilian | 智联招聘"