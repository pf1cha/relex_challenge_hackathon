# User Interface and Functional Requirements

## 1. Document Library

The system shall provide users with access to a dedicated document library where they can:

- View a list of documents available to them.
- Access documents based on their assigned project rights.
- Identify which documents are available for interaction with the AI assistant.
- Open an available document directly from the document list.

A **Basic User has no access to project documents by default**.

Document access must be granted through explicit **Project Rights**.

The document library should provide a clear and intuitive interface for browsing and accessing authorized documents.

---

## 2. AI Chat Interface

The system shall provide an AI-powered chat interface where users can interact with the AI assistant using natural language.

### 2.1 Document References and Citations

When generating a response, the AI assistant may reference information from documents that the current user is authorized to access.

Document references should be presented in a way similar to modern AI assistants.

The interface should include:

- A citation indicator associated with the relevant part of the AI-generated response.
- A citation marker or icon displayed next to the referenced text.
- A contextual preview available either:
  - in a right-hand sidebar; or
  - as a pop-up/hover window when the user interacts with the citation.

The citation preview should contain:

- The name or title of the referenced document.
- A link to the original document.
- The relevant excerpt from the document used to generate the response.

### 2.2 Document Access from Citations

When the user clicks on a referenced document:

- The document should open in a new browser window or tab.
- The document should only be accessible if the user has the required project rights.
- If the user does not have permission to access the document, the system should prevent unauthorized access and display an appropriate access-denied message.

The citation mechanism should make it easy for users to understand **where the AI-generated information originated** and allow them to verify the source.

---

# 3. Project Visualization

The system shall provide a dedicated project visualization interface.

## 3.1 Project Access

Project access is permission-based.

A **Basic User does not have access to any projects by default**.

A Basic User can receive access to one or more projects through explicit **Project Rights** granted by an Administrator.

Once a Basic User has been granted rights to a project, the user can:

- View the assigned project.
- Access documents associated with that project.
- Interact with authorized project documents through the AI assistant.
- View project-related visualizations, where applicable.

Users should only see projects for which they have explicit rights.

## 3.2 Project Selection

The project interface should allow authorized users to:

- View a list of projects available to them.
- Select a project.
- Open the corresponding project visualization.
- View project-related information based on their permissions.

Projects to which the user has no access should not be displayed.

---

# 4. Administration Interface

The Administration Interface shall be available exclusively to users with the **Administrator** role.

Administrators should have access to additional functionality for managing:

- Documents.
- Document availability for AI agents.
- Users.
- Clients.
- Employees.
- Project rights.
- Project assignments.

---

## 4.1 Document Management

Administrators shall be able to manage documents available within the system.

The document management interface should allow administrators to:

- View all documents in the system.
- View document information and status.
- Activate individual documents for AI-agent access.
- Deactivate documents for AI-agent access.
- Permanently delete documents.

### Document Status

Each document should clearly display its current status:

- **Active** — available for AI-agent processing.
- **Inactive** — stored in the system but not available to AI agents.

### Document Actions

Administrators should have access to actions such as:

- `Activate`
- `Deactivate`
- `Delete`

Permanent deletion should require an explicit confirmation step to prevent accidental removal.

---

# 5. User Management

Administrators shall have access to a dedicated user management interface.

The user management interface should allow administrators to:

- View users.
- View client and employee records.
- View the organization associated with a user.
- View the user's current project rights.
- Assign project rights.
- Remove project rights.
- Manage project assignments.

Basic Users should not have access to the user management interface.

---

# 6. Project Rights Management

Project access should be controlled through **Project Rights**.

Each project can have its own project-specific permission or role.

Administrators should be able to grant or revoke project rights for Basic Users.

The Project Rights interface should allow administrators to:

- Select a user.
- View the projects available in the system.
- View the projects to which the user currently has access.
- Grant access to a project.
- Revoke access to a project.
- View the user's current project permissions.

### Permission Logic

The permission model should follow these rules:

1. A **Basic User has no project access by default**.
2. A Basic User cannot access documents belonging to projects to which they have no rights.
3. A Basic User can be granted access to one or more projects by an Administrator.
4. Project Rights determine which projects the user can access.
5. Project Rights determine which documents the user can access.
6. Project Rights determine which project documents can be used by the AI assistant for that user.
7. Project Rights determine which project visualizations the user can access.
8. Revoking project access removes the user's access to the corresponding project and its documents.
9. Administrators can manage project rights for all users.

---

# 7. Client and Employee Management

Administrators should have a dedicated interface for managing client and employee access to projects.

The interface should allow administrators to:

- View clients and employees.
- Search and filter users.
- Select a client or employee.
- View their current project assignments.
- Assign them to a project.
- Assign them to multiple projects where applicable.
- Remove them from a project.
- Remove their information from the system.

Destructive actions, such as deleting a client or employee, should require explicit confirmation.

---

# 8. User Roles and Permissions

The system shall support the following primary user roles:

### Administrator

Administrators have access to administrative functionality and can manage:

- Documents.
- Document AI availability.
- Users.
- Clients.
- Employees.
- Projects.
- Project Rights.
- Project assignments.

### Basic User

A Basic User has access to the standard application interface but **does not have access to project information or project documents by default**.

A Basic User can receive access to projects through explicit Project Rights.

Once Project Rights are granted, the Basic User can access the corresponding:

- Project.
- Project documents.
- AI functionality related to those documents.
- Project visualizations.

---

# 9. User Permissions Matrix

| Functionality | Basic User | Basic User with Project Rights | Administrator |
|---|:---:|:---:|:---:|
| Access the application | ✓ | ✓ | ✓ |
| Use AI Chat | ✓ | ✓ | ✓ |
| View projects | — | ✓ | ✓ |
| View assigned project visualizations | — | ✓ | ✓ |
| View project documents | — | ✓ | ✓ |
| Interact with project documents through AI | — | ✓ | ✓ |
| View document citations | — | ✓ | ✓ |
| Open authorized source documents | — | ✓ | ✓ |
| Access projects without rights | — | — | ✓ |
| Access documents without project rights | — | — | ✓ |
| View all documents | — | — | ✓ |
| Activate documents for AI agents | — | — | ✓ |
| Deactivate documents for AI agents | — | — | ✓ |
| Delete documents | — | — | ✓ |
| Access user management | — | — | ✓ |
| Manage clients and employees | — | — | ✓ |
| Grant project rights | — | — | ✓ |
| Revoke project rights | — | — | ✓ |
| Assign users to projects | — | — | ✓ |
| Remove users from projects | — | — | ✓ |
| Delete client/employee information | — | — | ✓ |

> **Important:** A Basic User can access and use the AI Chat interface without having any Project Rights. However, without Project Rights, the user cannot access project documents, project information, or use project documents as sources for AI responses.

---

# 10. General UX Requirements

The interface should follow modern web application and AI-assistant design principles, with an emphasis on:

- Clear navigation between Documents, AI Chat, Projects, and Administration.
- Consistent visual language across all sections.
- Responsive and intuitive interactions.
- Clear indication of user permissions and document availability.
- Contextual document citations and previews.
- Confirmation dialogs for destructive actions.
- Appropriate loading, error, and access-denied states.
- Clear separation between standard user functionality and administrator functionality.
- Project-based access control.
- Clear indication of which projects are currently available to the user.
- Immediate UI updates when project rights are granted or revoked.

The overall interface should provide a **secure, intuitive, and modern user experience** while maintaining clear traceability between AI-generated responses and their underlying source documents.