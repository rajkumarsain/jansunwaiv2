"""empty message

Revision ID: 3896a0ebd7cd
Revises: 
Create Date: 2024-10-14 13:25:22.522405

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3896a0ebd7cd'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(None, 'department', ['department_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('department_id')

    # ### end Alembic commands ###
