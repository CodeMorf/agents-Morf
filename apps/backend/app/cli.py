import asyncio
import re

import typer
from sqlalchemy import select

from app.core.database import SessionLocal, create_schema
from app.core.security import hash_password
from app.models import Membership, Organization, Role, User

app = typer.Typer(help="Agents Morf administrative commands")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


async def _create_admin(email: str, password: str, organization: str):
    await create_schema()
    async with SessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == email.lower()))
        ).scalar_one_or_none()
        if existing:
            raise typer.BadParameter("A user with this email already exists")
        org_slug = slugify(organization)
        org = (
            await db.execute(select(Organization).where(Organization.slug == org_slug))
        ).scalar_one_or_none()
        if not org:
            org = Organization(name=organization, slug=org_slug, plan="enterprise")
            db.add(org)
            await db.flush()
        user = User(
            email=email.lower(),
            full_name="Platform Administrator",
            password_hash=hash_password(password),
            is_superuser=True,
        )
        db.add(user)
        await db.flush()
        db.add(Membership(organization_id=org.id, user_id=user.id, role=Role.super_admin))
        await db.commit()
        typer.echo(f"Created administrator {email} for organization {organization} ({org.id})")


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., "--email"),
    password: str = typer.Option(..., "--password"),
    organization: str = typer.Option("CodeMorf", "--organization"),
):
    """Create the first platform administrator (superuser)."""
    if len(password) < 12:
        raise typer.BadParameter("Password must contain at least 12 characters")
    asyncio.run(_create_admin(email, password, organization))


# Typer with a single command flattens to root options. Support both:
#   python -m app.cli create-admin --email ... --password ...
#   python -m app.cli --email ... --password ...
@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    email: str | None = typer.Option(None, "--email"),
    password: str | None = typer.Option(None, "--password"),
    organization: str = typer.Option("CodeMorf", "--organization"),
):
    if ctx.invoked_subcommand is not None:
        return
    if email and password:
        create_admin(email=email, password=password, organization=organization)
        return
    typer.echo(ctx.get_help())
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
