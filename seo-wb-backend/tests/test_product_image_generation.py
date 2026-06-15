from io import BytesIO

import pytest
from PIL import Image

from app.core.config import Settings
from app.core.errors import AppError
from app.services.billing_foundation import IMAGE_JOB_QUEUE_HIGH, IMAGE_JOB_QUEUE_LOW, IMAGE_JOB_QUEUE_NORMAL
from app.services.product_image_generator import IMAGE_JOB_QUEUE_KEY, ProductImageGenerator
from app.workers.image_generation_worker import IMAGE_JOB_PROCESSING_QUEUE, pop_next_image_job, recover_abandoned_jobs
from app.services.product_image_prompt_builder import build_product_image_prompt, product_family


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.queue = []
        self.locks = set()
        self.zsets = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def rpush(self, key, value):
        self.queue.append((key, value))
        return len(self.queue)

    async def lpop(self, key):
        for index, (queue_name, value) in enumerate(self.queue):
            if queue_name == key:
                self.queue.pop(index)
                return value
        return None

    async def delete(self, key):
        self.values.pop(key, None)
        return 1

    async def expire(self, key, seconds):
        return key in self.values

    async def lmove(self, source, destination, wherefrom, whereto):
        value = await self.lpop(source)
        if value is not None:
            self.queue.append((destination, value))
        return value

    async def lrem(self, key, count, value):
        before = len(self.queue)
        self.queue = [(queue_name, item) for queue_name, item in self.queue if not (queue_name == key and item == value)]
        return before - len(self.queue)

    async def lrange(self, key, start, end):
        return [value for queue_name, value in self.queue if queue_name == key]

    async def eval(self, script, numkeys, key, now, limit, expires_at, token, ttl):
        members = self.zsets.setdefault(key, {})
        members = {item: score for item, score in members.items() if score > float(now)}
        self.zsets[key] = members
        if len(members) >= int(limit):
            return 0
        members[token] = float(expires_at)
        return 1

    async def zrem(self, key, token):
        return self.zsets.setdefault(key, {}).pop(token, None) is not None


def _image_bytes() -> bytes:
    image = Image.new("RGB", (32, 48), color=(240, 240, 240))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _settings() -> Settings:
    return Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        openai_api_key="test-openai-key",
        redis_url="redis://localhost:6379/0",
        cloudinary_cloud_name=None,
        cloudinary_api_key=None,
        cloudinary_api_secret=None,
        cloud_dinary_name=None,
        cloud_dinary_api_key=None,
        cloud_dinary_api_secret=None,
    )


def test_prompt_builder_hero_rules_for_bottoms():
    prompt = build_product_image_prompt(
        {"title": "Брюки женские", "category": "Брюки", "color": "черный", "material": "хлопок"},
        0,
        4,
        True,
    )

    assert product_family("Брюки") == "bottoms"
    assert "main Wildberries hero image" in prompt
    assert "waist to shoes" in prompt
    assert "Do not redesign the product" in prompt
    assert "No text, watermark" in prompt


@pytest.mark.anyio
async def test_create_job_enqueues_and_sets_per_card_lock():
    redis = FakeRedis()
    generator = ProductImageGenerator(_settings(), redis)

    job = await generator.create_job(
        user_id=1,
        store_id=3,
        draft_id=3,
        variant_id="variant-1",
        variant_index=0,
        quantity=2,
        metadata={"title": "Test"},
        front_image=_image_bytes(),
        back_image=_image_bytes(),
        model_image=None,
    )

    assert job["status"] == "queued"
    assert job["total"] == 2
    assert redis.queue == [(IMAGE_JOB_QUEUE_KEY, job["id"])]

    with pytest.raises(AppError) as exc_info:
        await generator.create_job(
            user_id=1,
            store_id=2,
            draft_id=3,
            variant_id="variant-1",
            variant_index=0,
            quantity=1,
            metadata={"title": "Test"},
            front_image=_image_bytes(),
            back_image=_image_bytes(),
            model_image=None,
        )

    assert exc_info.value.code == "image_generation_already_running"


@pytest.mark.anyio
async def test_create_job_routes_to_requested_priority_queue():
    redis = FakeRedis()
    generator = ProductImageGenerator(_settings(), redis)

    agency_job = await generator.create_job(
        user_id=1,
        store_id=2,
        draft_id=3,
        variant_id="variant-1",
        variant_index=0,
        quantity=1,
        metadata={"title": "Agency"},
        front_image=_image_bytes(),
        back_image=_image_bytes(),
        queue_name=IMAGE_JOB_QUEUE_HIGH,
        credit_cost=1,
    )
    free_job = await generator.create_job(
        user_id=2,
        store_id=3,
        draft_id=4,
        variant_id="variant-2",
        variant_index=0,
        quantity=1,
        metadata={"title": "Free"},
        front_image=_image_bytes(),
        back_image=_image_bytes(),
        queue_name=IMAGE_JOB_QUEUE_LOW,
        credit_cost=1,
    )

    assert redis.queue[0] == (IMAGE_JOB_QUEUE_HIGH, agency_job["id"])
    assert redis.queue[1] == (IMAGE_JOB_QUEUE_LOW, free_job["id"])


@pytest.mark.anyio
async def test_create_job_allows_different_shops_but_blocks_same_shop():
    redis = FakeRedis()
    generator = ProductImageGenerator(_settings(), redis)

    await generator.create_job(
        user_id=1,
        store_id=10,
        draft_id=1,
        variant_id="variant-a",
        variant_index=0,
        quantity=1,
        metadata={"title": "A"},
        front_image=_image_bytes(),
    )
    await generator.create_job(
        user_id=1,
        store_id=11,
        draft_id=2,
        variant_id="variant-b",
        variant_index=0,
        quantity=1,
        metadata={"title": "B"},
        front_image=_image_bytes(),
    )

    with pytest.raises(AppError) as exc_info:
        await generator.create_job(
            user_id=2,
            store_id=10,
            draft_id=3,
            variant_id="variant-c",
            variant_index=0,
            quantity=1,
            metadata={"title": "C"},
            front_image=_image_bytes(),
        )

    assert exc_info.value.code == "store_image_generation_already_running"


@pytest.mark.anyio
async def test_worker_priority_pop_prefers_high_then_normal_then_low():
    redis = FakeRedis()
    await redis.rpush(IMAGE_JOB_QUEUE_LOW, "low-job")
    await redis.rpush(IMAGE_JOB_QUEUE_NORMAL, "normal-job")
    await redis.rpush(IMAGE_JOB_QUEUE_HIGH, "high-job")

    first = await pop_next_image_job(redis)
    second = await pop_next_image_job(redis)
    third = await pop_next_image_job(redis)

    assert first == (IMAGE_JOB_QUEUE_HIGH, "high-job")
    assert second == (IMAGE_JOB_QUEUE_NORMAL, "normal-job")
    assert third == (IMAGE_JOB_QUEUE_LOW, "low-job")


@pytest.mark.anyio
async def test_worker_recovers_abandoned_processing_job():
    redis = FakeRedis()
    state = {
        "id": "abandoned-job",
        "status": "processing",
        "step": "generating_front",
        "queue_name": IMAGE_JOB_QUEUE_NORMAL,
    }
    await redis.set("image_generation_job:abandoned-job", __import__("json").dumps(state))
    await redis.rpush(IMAGE_JOB_PROCESSING_QUEUE, "abandoned-job")

    recovered = await recover_abandoned_jobs(redis)

    assert recovered == 1
    assert (IMAGE_JOB_QUEUE_NORMAL, "abandoned-job") in redis.queue


@pytest.mark.anyio
async def test_worker_status_transitions(monkeypatch):
    redis = FakeRedis()
    generator = ProductImageGenerator(_settings(), redis)
    job = await generator.create_job(
        user_id=1,
        store_id=2,
        draft_id=3,
        variant_id="variant-1",
        variant_index=0,
        quantity=1,
        metadata={"title": "Test"},
        front_image=_image_bytes(),
        back_image=_image_bytes(),
        model_image=None,
    )

    monkeypatch.setattr(generator, "_generate_one", lambda *args, **kwargs: _image_bytes())
    monkeypatch.setattr(generator, "_attach_to_draft", lambda *args, **kwargs: None)

    result = await generator.run_job(job["id"], db=None)

    assert result["status"] == "completed"
    assert result["progress"] == 1
    assert result["images"][0]["url"].endswith("/generated-01.jpg")


@pytest.mark.anyio
async def test_gpt_image_openai_job_routing(monkeypatch):
    from app.services.gpt_image_catalog import GPTImageCatalogService
    redis = FakeRedis()
    generator = ProductImageGenerator(_settings(), redis)
    job = await generator.create_job(
        user_id=1,
        store_id=2,
        draft_id=3,
        variant_id="variant-1",
        variant_index=0,
        quantity=3,
        metadata={
            "title": "Test Product",
            "style": "studio",
            "garment_json": {
                "product_type": "skirt",
                "garment_area": "lower_body",
                "main_color": "black",
                "material": "cotton",
            }
        },
        front_image=_image_bytes(),
        back_image=_image_bytes(),
        model_image=None,
        job_type="gpt_image_openai",
    )

    assert job["job_type"] == "gpt_image_openai"

    async def mock_run_gpt_image_job(self, job_id, db, state, save_state_fn, attach_draft_fn, use_openai=False):
        assert use_openai is True
        state["status"] = "completed"
        state["step"] = "completed"
        state["progress"] = 3
        state["images"] = [{"url": "/media/generated-01.jpg"}]
        await save_state_fn(job_id, state)
        return state

    monkeypatch.setattr(GPTImageCatalogService, "run_gpt_image_job", mock_run_gpt_image_job)

    result = await generator.run_job(job["id"], db=None)
    assert result["status"] == "completed"
    assert result["job_type"] == "gpt_image_openai"


def test_gpt_prompt_builder_realism_and_retry():
    from app.services.gpt_prompt_builder import GPTPromptBuilder
    
    garment_json = {
        "product_type": "Платье",
        "category": "Платья",
        "gender": "женский (women/female)",
        "garment_area": "full_body",
        "main_color": "красный",
        "material": "шелк",
    }
    
    prompt = GPTPromptBuilder.build_prompt(
        garment_json=garment_json,
        style="studio",
        pose="front"
    )
    
    assert "Use the first image as the exact model reference." in prompt
    assert "Preserve the model's real face, identity, skin texture" in prompt
    assert "No plastic skin." in prompt
    assert "No CGI." in prompt
    assert "No 3D render." in prompt
    
    # Test build_strong_realism_prompt
    strong_prompt = GPTPromptBuilder.build_strong_realism_prompt(
        garment_json=garment_json,
        style="studio",
        pose="front"
    )
    assert "Use image 2 as the exact product reference." in strong_prompt
    assert "No CGI." in strong_prompt


@pytest.mark.anyio
async def test_gpt_image_catalog_service_requires_model(tmp_path, monkeypatch):
    from app.services.gpt_image_catalog import GPTImageCatalogService
    from app.core.config import Settings
    from app.core.errors import AppError
    
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        openai_api_key="test",
        fal_key="test",
        redis_url="redis://localhost:6379/0",
    )
    
    # Mock settings and directories
    monkeypatch.setattr("app.services.gpt_image_catalog.IMAGE_JOB_STORAGE_DIR", tmp_path)
    
    service = GPTImageCatalogService(settings)
    
    job_id = "test-job-id"
    job_dir = tmp_path / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True)
    
    # Create front image
    front_path = input_dir / "front.jpg"
    front_path.write_bytes(b"front")
    
    # Do NOT create model image
    
    state = {"status": "queued", "total": 3, "metadata": {"style": "studio"}}
    
    async def mock_save_state(jid, s):
        pass
        
    def mock_attach_draft(db, s, images):
        pass
        
    with pytest.raises(AppError) as exc_info:
        await service.run_gpt_image_job(
            job_id=job_id,
            db=None,
            state=state,
            save_state_fn=mock_save_state,
            attach_draft_fn=mock_attach_draft,
            use_openai=True
        )
        
    assert exc_info.value.code == "missing_model_reference"
    assert "Please select a real model reference" in exc_info.value.message
