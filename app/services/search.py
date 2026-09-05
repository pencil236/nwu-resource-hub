import math

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Resource, ResourceChunk, ResourceDislike, ResourceLike, ResourceStatus
from app.schemas import ResourceView, SearchResult
from app.services.embeddings import embed_texts


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


def search_resources(
    db: Session,
    query: str,
    course: str | None = None,
    category: str | None = None,
    file_type: str | None = None,
    limit: int = 10,
    viewer_id: str | None = None,
    resource_type: str | None = None,
    college: str | None = None,
    major: str | None = None,
    teacher: str | None = None,
    grade: str | None = None,
    year: int | None = None,
    sort_by: str = "relevance",
) -> list[SearchResult]:
    base_filters = [Resource.status == ResourceStatus.PUBLISHED]
    if course:
        base_filters.append(Resource.course.ilike(f"%{course}%"))
    if category:
        base_filters.append(Resource.category == category)
    if file_type:
        normalized_type = file_type.lower().lstrip(".")
        base_filters.append(Resource.original_filename.ilike(f"%.{normalized_type}"))
    for column, value in (
        (Resource.resource_type, resource_type),
        (Resource.college, college),
        (Resource.major, major),
        (Resource.teacher, teacher),
        (Resource.grade, grade),
    ):
        if value:
            base_filters.append(column.ilike(f"%{value}%"))
    if year:
        base_filters.append(Resource.year == year)

    keyword_stmt = (
        select(Resource)
        .where(
            *base_filters,
            or_(
                Resource.title.ilike(f"%{query}%"),
                Resource.description.ilike(f"%{query}%"),
                Resource.experience.ilike(f"%{query}%"),
                Resource.tags.ilike(f"%{query}%"),
            ),
        )
        .limit(limit)
    )
    keyword_resources = db.scalars(keyword_stmt).all()

    query_vector = embed_texts([query])[0]
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        chunk_stmt = (
            select(ResourceChunk)
            .join(Resource)
            .where(*base_filters, ResourceChunk.embedding.is_not(None))
            .order_by(ResourceChunk.embedding.cosine_distance(query_vector))
            .limit(limit * 3)
        )
        semantic_chunks = db.scalars(chunk_stmt).all()
        semantic_scores: dict[str, float] = {}
        for chunk in semantic_chunks:
            if chunk.embedding is None:
                continue
            score = max(0.0, 1.0 - _cosine_distance(chunk.embedding, query_vector))
            semantic_scores[chunk.resource_id] = max(
                semantic_scores.get(chunk.resource_id, 0.0), score
            )
    else:
        chunk_stmt = (
            select(ResourceChunk)
            .join(Resource)
            .where(*base_filters, ResourceChunk.embedding.is_not(None))
            .limit(500)
        )
        semantic_chunks = db.scalars(chunk_stmt).all()
        semantic_scores: dict[str, float] = {}
        for chunk in semantic_chunks:
            if chunk.embedding is None:
                continue
            score = _cosine(list(chunk.embedding), query_vector)
            semantic_scores[chunk.resource_id] = max(
                semantic_scores.get(chunk.resource_id, -1.0), score
            )

    resource_ids = {
        resource_id for resource_id, score in semantic_scores.items() if score >= 0.05
    } | {resource.id for resource in keyword_resources}
    if not resource_ids:
        return []
    resources = db.scalars(select(Resource).where(Resource.id.in_(resource_ids))).all()
    liked_ids: set[str] = set()
    disliked_ids: set[str] = set()
    if viewer_id:
        liked_ids = set(
            db.scalars(
                select(ResourceLike.resource_id).where(
                    ResourceLike.user_id == viewer_id,
                    ResourceLike.resource_id.in_(resource_ids),
                )
            ).all()
        )
        disliked_ids = set(
            db.scalars(
                select(ResourceDislike.resource_id).where(
                    ResourceDislike.user_id == viewer_id,
                    ResourceDislike.resource_id.in_(resource_ids),
                )
            ).all()
        )
    keyword_ids = {resource.id for resource in keyword_resources}
    chunk_by_resource = {chunk.resource_id: chunk.content[:300] for chunk in semantic_chunks}
    results = [
        SearchResult(
            resource=ResourceView.model_validate(resource).model_copy(
                update={
                    "liked_by_me": resource.id in liked_ids,
                    "disliked_by_me": resource.id in disliked_ids,
                    "owner_name": "匿名同学"
                    if resource.is_anonymous
                    else resource.owner.display_name,
                }
            ),
            score=round(
                (0.45 if resource.id in keyword_ids else 0)
                + 0.55 * max(0, semantic_scores.get(resource.id, 0)),
                4,
            ),
            matched_excerpt=chunk_by_resource.get(resource.id),
        )
        for resource in resources
    ]
    if sort_by == "likes":
        return sorted(
            results,
            key=lambda item: (item.resource.like_count, item.resource.created_at),
            reverse=True,
        )[:limit]
    if sort_by == "newest":
        return sorted(results, key=lambda item: item.resource.created_at, reverse=True)[:limit]
    return sorted(results, key=lambda item: item.score, reverse=True)[:limit]


def _cosine_distance(left, right: list[float]) -> float:
    return 1.0 - _cosine(list(left), right)
