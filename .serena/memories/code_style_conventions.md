# Code Style & Conventions

## Python Backend Style

### Naming Conventions
- **Classes**: PascalCase (e.g., `TaskService`, `VideoProcessor`)
- **Functions/Methods**: snake_case (e.g., `get_task_details()`, `process_video()`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `TEMP_DIR`, `MAX_CLIP_DURATION`)
- **Private members**: Leading underscore (e.g., `_internal_method()`)
- **Database fields**: snake_case for tasks/clips tables, camelCase for Better Auth tables

### Type Hints
- **Required**: All function signatures should have type hints
- **Pattern**: `async def function_name(param: Type) -> ReturnType:`
- **Examples**:
  ```python
  async def create_task(user_id: str, url: str) -> Dict[str, Any]:
  async def get_task(task_id: str, db: AsyncSession) -> Optional[Task]:
  ```
- **Imports**: Use `from typing import Dict, Any, Optional, List` etc.

### Docstrings
- **Style**: Google-style docstrings for public methods
- **Pattern**:
  ```python
  """Brief description.
  
  Longer description if needed.
  
  Args:
      param_name: Description.
  
  Returns:
      Description of return value.
      
  Raises:
      ExceptionType: When this occurs.
  """
  ```

### Code Organization
- **Imports**: Standard library → Third-party → Local imports (PEP 8)
- **Async/Await**: Always use async for I/O operations
- **Database**: Use AsyncSession context managers
- **Error Handling**: Use FastAPI HTTPException for API errors
- **Logging**: Use logger.info(), logger.error(), logger.warning() with emoji prefixes

### Emoji Logging (Backend Convention)
- 🚀 = Starting operation
- ✅ = Success
- ❌ = Error
- 📝 = Data/information
- 💾 = Database operation
- 🎬 = Video processing
- 🤖 = AI operation
- ⬇️ = Download
- 📊 = Status/progress
- 🔍 = Checking/searching
- 📺 = YouTube/video source
- 🔗 = Linking/connecting
- 🎉 = Completion/success
- ⚠️ = Warning

## TypeScript/React Frontend Style

### Naming Conventions
- **Components**: PascalCase (e.g., `TaskDetail`, `UploadButton`)
- **Files**: kebab-case for page/component files (e.g., `task-detail.tsx`, `dynamic-video-player.tsx`)
- **Functions/Hooks**: camelCase (e.g., `useTaskData()`, `handleUpload()`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_FONT_SIZE`, `MAX_FILE_SIZE`)
- **Variables**: camelCase (e.g., `taskId`, `isLoading`)

### Type Hints
- **Required**: All components and functions should have TypeScript types
- **Pattern**: `interface Props { ... }` or `type Props = { ... }`
- **React Components**: 
  ```typescript
  interface TaskDetailProps {
    taskId: string;
    onComplete?: () => void;
  }
  
  export function TaskDetail({ taskId, onComplete }: TaskDetailProps) {
    // Component code
  }
  ```

### Code Organization
- **Structure**: Separate components, hooks, lib utilities, and pages
- **Imports**: Next.js → React → Third-party → Local
- **Server/Client**: Use 'use client' directive for client components
- **Forms**: Use HTML forms with Next.js actions where possible
- **Styling**: TailwindCSS classes, use ShadCN UI components when available

### React 19 / Next.js 15 Patterns
- **App Router**: Use app/ directory structure
- **Server Components**: Default to server components, 'use client' only when needed
- **Turbopack**: Development server uses Turbopack (faster builds)
- **Dynamic Imports**: For large components: `const Component = dynamic(() => import('...'))`

## Git Conventions

### Commit Messages
- **Format**: Descriptive, present tense
- **Examples**:
  - "Add clip list endpoint" (new feature)
  - "Fix face detection fallback" (bug fix)
  - "Refactor video processing pipeline" (refactoring)
  - "Update documentation" (docs)

### Branches
- **Main branch**: `main` (production-ready code)
- **Feature branches**: `feature/description` (new features)
- **Bug fixes**: `fix/description` (bug fixes)

## Database Conventions

### SQL Style
- **Keywords**: UPPERCASE (SELECT, FROM, WHERE, INSERT, UPDATE)
- **Table/Column Names**: Lower case with underscores (snake_case)
- **Ordering**: SELECT columns → FROM table → WHERE conditions → ORDER BY

### Schema Patterns
- **Timestamps**: created_at, updated_at (TIMESTAMP WITH TIME ZONE)
- **IDs**: VARCHAR(36) for UUIDs
- **Booleans**: BOOLEAN (PostgreSQL native)
- **Foreign Keys**: Include ON DELETE CASCADE or ON DELETE SET NULL
- **Constraints**: CHECK constraints for valid values

## General Principles
1. **DRY**: Don't Repeat Yourself
2. **SOLID**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
3. **Error Handling**: Be explicit, log appropriately
4. **Performance**: Use async/await, avoid blocking operations
5. **Security**: Validate inputs, use parameterized queries, environment variables for secrets
