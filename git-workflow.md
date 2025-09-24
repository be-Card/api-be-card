# Git Workflow - BeCard API

## Estructura de Branches

```
main (producción)
├── develop (desarrollo)
│   ├── feature/auth-improvements
│   ├── feature/user-management
│   ├── feature/card-system
│   ├── hotfix/security-patch
│   └── bugfix/login-validation
```

## Flujo de Trabajo Visual

```mermaid
gitgraph
    commit id: "Initial commit"
    commit id: "API base setup"
    commit id: "JWT auth"
    
    branch develop
    checkout develop
    commit id: "Develop branch"
    
    branch feature/card-system
    checkout feature/card-system
    commit id: "Add card model"
    commit id: "Card endpoints"
    commit id: "Card validation"
    
    checkout develop
    merge feature/card-system
    commit id: "Merge card system"
    
    branch feature/user-profile
    checkout feature/user-profile
    commit id: "Profile endpoints"
    commit id: "Avatar upload"
    
    checkout develop
    merge feature/user-profile
    commit id: "Merge user profile"
    
    checkout main
    merge develop
    commit id: "Release v1.1.0"
```

## Tipos de Branches

### 🌟 **main** (Rama principal)
- **Propósito**: Código en producción
- **Estabilidad**: Siempre estable y deployable
- **Protección**: Solo merge desde `develop`
- **Tags**: Versiones de release (v1.0.0, v1.1.0, etc.)

### 🚀 **develop** (Rama de desarrollo)
- **Propósito**: Integración de features
- **Base para**: Todas las ramas de desarrollo
- **Merge desde**: feature/, bugfix/, hotfix/
- **Merge hacia**: main (releases)

### 🔧 **feature/** (Nuevas funcionalidades)
- **Nomenclatura**: `feature/nombre-descriptivo`
- **Base**: develop
- **Ejemplos**: 
  - `feature/card-management`
  - `feature/user-authentication`
  - `feature/api-documentation`

### 🐛 **bugfix/** (Corrección de bugs)
- **Nomenclatura**: `bugfix/descripcion-bug`
- **Base**: develop
- **Ejemplos**:
  - `bugfix/login-validation`
  - `bugfix/database-connection`

### 🚨 **hotfix/** (Correcciones urgentes)
- **Nomenclatura**: `hotfix/descripcion-urgente`
- **Base**: main (para fixes críticos en producción)
- **Merge hacia**: main Y develop

## Comandos Git para el Workflow

### Configuración inicial
```bash
# Crear rama develop desde main
git checkout main
git checkout -b develop
git push -u origin develop

# Proteger ramas principales (en GitHub/GitLab)
# - main: Require PR, require reviews
# - develop: Require PR
```

### Trabajar en una nueva feature
```bash
# 1. Crear rama feature desde develop
git checkout develop
git pull origin develop
git checkout -b feature/card-system

# 2. Desarrollar y commitear
git add .
git commit -m "feat: add card model and endpoints"
git push -u origin feature/card-system

# 3. Crear Pull Request hacia develop
# (Desde GitHub/GitLab interface)

# 4. Después del merge, limpiar
git checkout develop
git pull origin develop
git branch -d feature/card-system
```

### Trabajar en bugfix
```bash
# 1. Crear rama bugfix desde develop
git checkout develop
git pull origin develop
git checkout -b bugfix/login-validation

# 2. Corregir y commitear
git add .
git commit -m "fix: validate email format in login"
git push -u origin bugfix/login-validation

# 3. PR hacia develop
```

### Hotfix urgente
```bash
# 1. Crear hotfix desde main
git checkout main
git pull origin main
git checkout -b hotfix/security-patch

# 2. Corregir y commitear
git add .
git commit -m "hotfix: fix security vulnerability"
git push -u origin hotfix/security-patch

# 3. PR hacia main
# 4. Después del merge a main, también merge a develop
git checkout develop
git merge main
git push origin develop
```

### Release (develop → main)
```bash
# 1. Asegurar que develop está actualizado y testeado
git checkout develop
git pull origin develop

# 2. Crear PR de develop hacia main
# 3. Después del merge, crear tag de versión
git checkout main
git pull origin main
git tag -a v1.1.0 -m "Release version 1.1.0"
git push origin v1.1.0
```

## Convenciones de Commits

### Formato
```
tipo(scope): descripción

[cuerpo opcional]

[footer opcional]
```

### Tipos de commits
- **feat**: Nueva funcionalidad
- **fix**: Corrección de bug
- **docs**: Cambios en documentación
- **style**: Cambios de formato (no afectan funcionalidad)
- **refactor**: Refactoring de código
- **test**: Agregar o modificar tests
- **chore**: Tareas de mantenimiento

### Ejemplos
```bash
git commit -m "feat(auth): add JWT token refresh endpoint"
git commit -m "fix(user): validate email format on registration"
git commit -m "docs(api): update authentication examples"
git commit -m "refactor(database): optimize user queries"
```

## Pull Request Template

```markdown
## Descripción
Breve descripción de los cambios realizados.

## Tipo de cambio
- [ ] Bug fix (cambio que corrige un issue)
- [ ] Nueva feature (cambio que agrega funcionalidad)
- [ ] Breaking change (fix o feature que causa cambios incompatibles)
- [ ] Documentación

## Testing
- [ ] Tests unitarios pasan
- [ ] Tests de integración pasan
- [ ] Probado manualmente

## Checklist
- [ ] Código sigue las convenciones del proyecto
- [ ] Self-review realizado
- [ ] Documentación actualizada
- [ ] No hay console.logs o prints de debug
```

## Protección de Branches

### Configuración recomendada en GitHub/GitLab:

**Branch `main`:**
- ✅ Require pull request reviews (mínimo 1)
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Restrict pushes that create files larger than 100MB
- ✅ Require signed commits

**Branch `develop`:**
- ✅ Require pull request reviews
- ✅ Require status checks to pass
- ✅ Allow force pushes (solo para maintainers)