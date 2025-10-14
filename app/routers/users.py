"""
Router para operaciones CRUD de usuarios
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session

from app.core.database import get_session
from app.services.users import UserService
from app.models.user_extended import Usuario
from app.routers.auth import get_current_user
from app.schemas.users import (
    UserCreate,
    UserUpdate,
    UserRead,
    UserWithRoles,
    MessageResponse,
    UserListResponse,
    RoleAssignment,
    PasswordChange
)
from app.routers.auth import get_current_active_user, require_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin)
):
    """
    Crear un nuevo usuario
    
    - **nombre_usuario**: Nombre de usuario único
    - **email**: Email único
    - **password**: Contraseña (mínimo 8 caracteres)
    - **nombre**: Nombre del usuario
    - **apellido**: Apellido del usuario
    - **sexo**: Sexo del usuario (FEMENINO/MASCULINO)
    - **fecha_nacimiento**: Fecha de nacimiento
    - **telefono**: Teléfono opcional
    """
    # Verificar si el email ya existe
    existing_user = UserService.get_user_by_email(session, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Verificar si el nombre de usuario ya existe
    existing_username = UserService.get_user_by_username(session, user.nombre_usuario)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya está registrado"
        )
    
    # Crear usuario
    db_user = UserService.create_user(
        session,
        nombre_usuario=user.nombre_usuario,
        email=user.email,
        password=user.password,
        nombre=user.nombre,
        apellido=user.apellido,
        sexo=user.sexo,
        fecha_nacimiento=user.fecha_nacimiento,
        telefono=user.telefono
    )
    
    return db_user


@router.get("/", response_model=UserListResponse)
def read_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    activo: bool = Query(default=None, description="Filtrar por estado activo"),
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin)
):
    """
    Obtener lista de usuarios con paginación
    
    - **skip**: Número de registros a omitir (paginación)
    - **limit**: Número máximo de registros a devolver
    - **activo**: Filtrar por estado activo (opcional)
    """
    users = UserService.get_users(session, skip=skip, limit=limit, activo=activo)
    
    # Contar total (para paginación)
    from sqlmodel import select, func
    from app.models.user_extended import Usuario
    statement = select(func.count()).select_from(Usuario)
    if activo is not None:
        statement = statement.where(Usuario.activo == activo)
    total = session.exec(statement).one()
    
    return UserListResponse(
        users=users,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{user_id}", response_model=UserWithRoles)
def read_user(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Obtener un usuario por ID con sus roles y nivel
    
    - **user_id**: ID del usuario
    
    Permiso: Usuario puede ver su propio perfil o admin puede ver cualquiera
    """
    # Verificar permisos: usuario puede ver su propio perfil o ser admin
    user_roles = UserService.get_user_roles(session, current_user.id)
    role_names = [role.tipo for role in user_roles]
    is_admin = "administrador" in role_names or "admin" in role_names
    
    if not is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este usuario"
        )
    
    user = UserService.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Obtener roles y nivel
    role_assignments = UserService.get_user_role_assignments(session, user_id)
    nivel = UserService.get_user_level(session, user_id)
    
    # Convertir a respuesta con mapeo correcto de campos
    user_dict = user.model_dump()
    # Convert UUID to string for id_ext
    user_dict["id_ext"] = str(user.id_ext)
    
    # Create roles data structure that matches frontend expectations
    roles_data = []
    for role_assignment in role_assignments:
        # Access the related TipoRolUsuario through the relationship
        role_type = role_assignment.rol
        role_data = {
            "id": role_assignment.id_rol,
            "tipo_rol_usuario": {
                "id": role_type.id,
                "nombre": role_type.tipo,  # Map 'tipo' to 'nombre' for frontend
                "descripcion": role_type.descripcion
            },
            "asignado_el": role_assignment.fecha_asignacion.isoformat()
        }
        roles_data.append(role_data)
    
    user_dict["roles"] = roles_data
    
    # Map nivel data with correct field names for frontend
    if nivel:
        nivel_dict = nivel.model_dump()
        # Map puntaje_min to puntaje_minimo for frontend compatibility
        nivel_dict["puntaje_minimo"] = nivel_dict.pop("puntaje_min")
        user_dict["nivel"] = nivel_dict
    else:
        user_dict["nivel"] = None
    
    return UserWithRoles(**user_dict)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    print(f"DEBUG: Iniciando update_user")
    print(f"DEBUG: user_id = {user_id}")
    print(f"DEBUG: user_update = {user_update}")
    print(f"DEBUG: current_user.id = {current_user.id}")
    
    try:
        # Verificar que el usuario solo pueda editar su propio perfil
        if current_user.id != user_id:
            print(f"DEBUG: Error de permisos - current_user.id ({current_user.id}) != user_id ({user_id})")
            raise HTTPException(status_code=403, detail="No tienes permisos para editar este perfil")
        
        print(f"DEBUG: Llamando a UserService.update_user")
        updated_user = UserService.update_user(
            session=db,
            user_id=user_id,
            nombres=user_update.nombres,
            apellidos=user_update.apellidos,
            telefono=user_update.telefono,
            email=user_update.email,
            password=user_update.password
        )
        
        print(f"DEBUG: UserService.update_user completado, resultado: {updated_user}")
        
        if not updated_user:
            print(f"DEBUG: Usuario no encontrado")
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        print(f"DEBUG: Creando respuesta UserRead")
        response = UserRead(
            id=updated_user.id,
            nombre_usuario=updated_user.nombre_usuario,
            email=updated_user.email,
            nombres=updated_user.nombres,
            apellidos=updated_user.apellidos,
            sexo=updated_user.sexo,
            fecha_nac=updated_user.fecha_nac,
            telefono=updated_user.telefono,
            id_ext=str(updated_user.id_ext),
            activo=updated_user.activo,
            verificado=updated_user.verificado,
            fecha_creacion=updated_user.fecha_creacion,
            ultimo_login=updated_user.ultimo_login,
            intentos_login_fallidos=updated_user.intentos_login_fallidos
        )
        print(f"DEBUG: Respuesta creada exitosamente")
        return response
        
    except HTTPException as he:
        print(f"DEBUG: HTTPException capturada: {he.detail}")
        raise
    except Exception as e:
        print(f"ERROR: Excepción no controlada: {str(e)}")
        print(f"ERROR: Tipo de excepción: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    hard: bool = Query(default=False, description="Eliminación física (irreversible)"),
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin)
):
    """
    Eliminar (desactivar) un usuario
    
    - **user_id**: ID del usuario
    - **hard**: Si es True, eliminación física (irreversible). Por defecto False (soft delete)
    """
    if hard:
        success = UserService.hard_delete_user(session, user_id)
        message = "Usuario eliminado permanentemente"
    else:
        success = UserService.delete_user(session, user_id)
        message = "Usuario desactivado"
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    return MessageResponse(message=message)


@router.post("/{user_id}/verify", response_model=MessageResponse)
def verify_user_email(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin)
):
    """
    Verificar el email de un usuario
    
    - **user_id**: ID del usuario
    """
    success = UserService.verify_user_email(session, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    return MessageResponse(message="Email verificado exitosamente")


@router.post("/{user_id}/roles", response_model=MessageResponse)
def add_role_to_user(
    user_id: int,
    role_assignment: RoleAssignment,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin)
):
    """
    Asignar un rol a un usuario
    
    - **user_id**: ID del usuario
    - **role_id**: ID del rol a asignar
    """
    success = UserService.add_role_to_user(
        session,
        user_id=user_id,
        role_id=role_assignment.role_id,
        assigned_by=current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario o rol no encontrado"
        )
    
    return MessageResponse(message="Rol asignado exitosamente")


@router.delete("/{user_id}/roles/{role_id}", response_model=MessageResponse)
def remove_role_from_user(
    user_id: int,
    role_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin)
):
    """
    Revocar un rol de un usuario
    
    - **user_id**: ID del usuario
    - **role_id**: ID del rol a revocar
    """
    success = UserService.remove_role_from_user(session, user_id, role_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación de rol no encontrada"
        )
    
    return MessageResponse(message="Rol revocado exitosamente")