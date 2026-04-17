# force-delete-win (Python)

`force-delete-win`은 Windows 10/11에서 삭제가 잠긴 파일/폴더를 **Python 3.10~3.14만으로** 강제 삭제하기 위한 도구입니다.

원본 `andfoy/force-delete-win`의 목적(잠금 상태의 파일/폴더 삭제)을 유지하되, Rust 확장 없이 순수 Python 구현으로 제공됩니다.

## 동작 방식

1. 일반 삭제(`Path.unlink` / `shutil.rmtree`)를 먼저 시도합니다.
2. 실패하면 Windows Restart Manager API(`Rstrtmgr.dll`)로 대상 경로를 점유 중인 프로세스 PID를 조회합니다.
3. 해당 프로세스를 `taskkill /F /T`로 종료합니다.
4. 삭제를 다시 시도합니다(기본 3회 재시도).

> ⚠️ 주의: 다른 프로그램 프로세스를 강제 종료하므로 데이터 손실이나 시스템 불안정이 발생할 수 있습니다.

## 요구 사항

- OS: Windows 10 / Windows 11
- Python: 3.10 이상 (3.10~3.14 지원)

## 설치

로컬 저장소에서 설치:

```bash
pip install .
```

## Python 사용 예시

```python
from force_delete_win import force_delete_file_folder

deleted = force_delete_file_folder(r"C:\temp\locked-folder")
print(deleted)  # True / False
```

## CLI 사용 예시

```bash
force-delete-win "C:\temp\locked-file.txt"
force-delete-win "C:\temp\locked-folder" --retries 5
```

종료 코드:

- `0`: 삭제 성공
- `1`: 삭제 실패
- `2`: 실행 환경 오류(예: Windows 아님)

## 점검

```bash
python -m compileall force_delete_win
```

## 라이선스

MIT (`LICENSE` 참고)
