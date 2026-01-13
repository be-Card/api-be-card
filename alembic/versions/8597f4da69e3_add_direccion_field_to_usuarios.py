"""add_direccion_field_to_usuarios

Revision ID: 8597f4da69e3
Revises: afbe24b40bc9
Create Date: 2025-10-20 14:53:44.157596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8597f4da69e3'
down_revision: Union[str, None] = 'afbe24b40bc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar campo direccion a la tabla usuarios
    op.add_column('usuarios', sa.Column('direccion', sa.Text(), nullable=True))
    
    # Crear índice para búsquedas por dirección (usando GIN para búsqueda de texto)
    op.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_direccion ON usuarios USING gin(to_tsvector('spanish', direccion)) WHERE direccion IS NOT NULL")


def downgrade() -> None:
    # Eliminar índice
    op.execute("DROP INDEX IF EXISTS idx_usuarios_direccion")
    
    # Eliminar columna direccion
    op.drop_column('usuarios', 'direccion')
