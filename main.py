from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, constr, Field
import asyncio
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

if os.getenv("ENVIRONMENT") == "production":
    SQLALCHEMY_DATABASE_URL = (os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://", 1) + "?sslmode=require")
else:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
app = FastAPI()

class Task(BaseModel):
    id: int
    title: str = constr(min_length=3, max_length=100)
    description: str = Field(max_length=300)
    status: str = "do wykonania"

    class Config:
        str_strip_whitespace = True

class Pomodoro(BaseModel):
    task_id: int
    start_time: datetime
    end_time: datetime
    completed: bool = False

tasks = []
statuses = ['do wykonania', 'w trakcie', 'zakończone']
pomodoro_sessions = []
active_timers = {}

def generate_id() -> int:
    return max([task.id for task in tasks], default=0) + 1

@app.post("/tasks")
async def create_task(task: Task):
    for item in tasks:
        if item.title == task.title:
            raise HTTPException(status_code=400, detail=f"Task with title '{item.title}' already exists")

    task.id = generate_id()
    tasks.append(task)
    return {"task_id": task.id, "task": task}

@app.get("/tasks")
async def get_tasks(status: Optional[str] = Query(None)):
    if status:
        if status not in statuses:
            raise HTTPException(status_code=400, detail=f"Task with status '{status}' does not exist")
        filtered_tasks = [task for task in tasks if task.status == status]
        return filtered_tasks
    else:
        return tasks


@app.get("/tasks/{task_id}")
async def get_task_info(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Task with ID {task_id} does not exist")

@app.put("/tasks/{task_id}")
async def update_task(task_id: int, updated_task: Task):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            for other_task in tasks:
                if other_task.title == updated_task.title and other_task.id != task_id:
                    raise HTTPException(status_code=400, detail=f"Task with title '{updated_task.title}' already exists")

            if updated_task.status not in statuses:
                raise HTTPException(status_code=400, detail=f"Invalid status '{updated_task.status}'")

            tasks[i] = updated_task
            updated_task.id = task_id
            return {"task_id": task_id, "task": updated_task}

    raise HTTPException(status_code=404, detail=f"Task with ID {task_id} does not exist")

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return {"detail": f"Task with ID {task_id} has been deleted"}

    raise HTTPException(status_code=404, detail=f"Task with ID {task_id} does not exist")


@app.post("/pomodoro")
async def create_pomodoro(pomodoro: Pomodoro):
    if any(task.id == pomodoro.task_id for task in tasks):
        if not any(session.task_id == pomodoro.task_id and not session.completed for session in pomodoro_sessions):
            pomodoro.start_time = datetime.now()
            pomodoro.end_time = datetime.now() + timedelta(minutes=25)
            pomodoro_sessions.append(pomodoro)

            timer_task = asyncio.create_task(end_pomodoro_async(pomodoro.task_id))
            active_timers[pomodoro.task_id] = timer_task

            return {'detail': f'New Pomodoro with ID {pomodoro.task_id} has been created'}
        raise HTTPException(status_code=400, detail="Previous Pomodoro sessions are not completed")

    raise HTTPException(status_code=404, detail=f"Task with ID {pomodoro.task_id} does not exist")


async def end_pomodoro_async(task_id: int):
    await asyncio.sleep(25 * 60)
    for session in pomodoro_sessions:
        if session.task_id == task_id and not session.completed:
            session.completed = True
            session.end_time = datetime.now()
            break
    active_timers.pop(task_id, None)


@app.post("/pomodoro/{task_id}/stop")
async def stop_pomodoro(task_id: int):
    if task_id in active_timers:
        active_timers[task_id].cancel()
        active_timers.pop(task_id, None)

        for session in pomodoro_sessions:
            if session.task_id == task_id and not session.completed:
                session.completed = True
                session.end_time = datetime.now()
                return {'detail': f"Pomodoro with ID {task_id} has been stopped"}

    raise HTTPException(status_code=404, detail=f"Pomodoro with ID {task_id} does not exist or is already completed")

@app.get("/pomodoro/stats")
async def get_pomodoro_stats():
    stats = {}
    for session in pomodoro_sessions:
        if session.completed:
            if session.task_id not in stats:
                stats[session.task_id] = {'Liczba sesji': 1, 'Czas spędzony': session.end_time - session.start_time}
            else:
                stats[session.task_id]['Liczba sesji'] += 1
                stats[session.task_id]['Czas spędzony'] += session.end_time - session.start_time

    return stats

@app.get("/pomodoro/sessions")
async def get_pomodoro_sessions():
    return pomodoro_sessions
