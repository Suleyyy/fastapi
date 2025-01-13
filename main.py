from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, constr, Field
import uuid

app = FastAPI()

class Task(BaseModel):
    title: str = constr(min_length=3, max_length=100)
    description: str = Field(max_length=300)
    status: str = "do wykonania"

    class Config:
        anystr_strip_whitespace = True


def generate_id() -> str:
    return str(uuid.uuid4())

tasks = {}
statuses = ['do wykonania', 'w trakcie', 'zakończone']
@app.post("/tasks")
async def create_task(task: Task):
    for item in tasks.values():
        if item.title == task.title:
            raise HTTPException(detail=f"{item.title} already exists")

    id = generate_id()
    tasks[id] = task
    return {"task_id": id, "task": task}

@app.get("/tasks")
async def get_tasks():
    return tasks

@app.get("/tasks/{task_id}")
async def get_task_info(id: str):
    if id not in tasks.keys():
        raise HTTPException(detail=f"{id} does not exist", status_code=404)
    return tasks[id]


@app.put("/tasks")
async def update_task(id: str, task: Task):
    if id not in tasks.keys():
        raise HTTPException(detail=f"{id} does not exist")
    for item in tasks.values():
        if item.title == task.title:
            raise HTTPException(detail=f"{item.title} already exists")
    if task.status not in statuses:
        raise HTTPException(detail=f"{task.status} does not exist")
    tasks[id] = task
    return {"task_id": id, "task": task}