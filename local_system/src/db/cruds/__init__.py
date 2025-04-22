#====================================================================================================#
# [ 파일 개요 ]
# 현재 디렉토리를 파이썬 패키지로 인식시키는 역할을 합니다.
# 이 패키지 내의 다른 모듈(event_crud, event_detail_crud, solution_crud)에 정의된 주요 CRUD(Create, Read, Update, Delete) 함수들을 임포트하여, 패키지 레벨에서 직접 접근할 수 있도록 re-export합니다.

# [ 주요 로직 흐름 ]
# 1. 파이썬 인터프리터가 이 디렉토리를 패키지로 처리하도록 함.
# 2. event_crud 모듈에서 이벤트 관련 CRUD 함수를 임포트.
# 3. event_detail_crud 모듈에서 이벤트 상세 정보 관련 CRUD 함수를 임포트.
# 4. solution_crud 모듈에서 해결 방안 CRUD 함수를 임포트.
# 5. 결과적으로, 이 패키지를 임포트하면 여기에 임포트된 모든 함수들을 패키지 네임스페이스를 통해 직접 사용할 수 있게 됩니다.
#    (예: import package.crud -> crud.create_event 사용 가능)
#====================================================================================================#


from .event_crud import create_event, get_event, get_events
from .event_detail_crud import (
    create_event_detail,
    get_event_detail,
    update_event_detail,
)
from .solution_crud import (
    create_solution,
    get_solution,
    update_solution,
    update_solution_complete,
)
