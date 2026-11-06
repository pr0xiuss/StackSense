import express from "express";

const router = express.Router();

class ProjectController {
  constructor(service) {
    this.service = service;
  }

  async listProjects(req, res) {
    const projects = await this.service.getAll();
    res.json({ data: projects });
  }
}

function configureRoutes(app, controller) {
  app.get("/projects", (req, res) => controller.listProjects(req, res));
}

export default router;

