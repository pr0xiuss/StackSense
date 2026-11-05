import { Request, Response } from "express";

export interface ProjectDto {
  id: string;
  name: string;
  ownerId: string;
}

export type ProjectStatus = "active" | "archived";

export class ProjectService {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  public async fetchProject(id: string): Promise<ProjectDto | null> {
    return { id, name: "Sample", ownerId: "user-1" };
  }
}

