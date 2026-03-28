from fastapi import APIRouter, HTTPException, Depends
from core.database import get_conn
from core.dependencies import get_current_user

router = APIRouter(prefix="/user", tags=["User"])
@router.post("/delete-request")
def request_delete_account(cur_user=Depends(get_current_user)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute("select 1 from DeleteAccountRequests " \
                    "where UserId = ? and Status = 'Pending' ",(cur_user["user_id"],))
        existed = curs.fetchone()
        if existed:
            raise HTTPException(400,"Ban da gui yeu cau truoc do")
        curs.execute("insert into DeleteAccountRequests(UserId, Status) " \
                    "values (?, 'Pending')", (cur_user["user_id"],))
        conn.commit()
        return {"message":"Da gui yeu cau xoa tai khoan"}
    finally:
        conn.close()
        
        