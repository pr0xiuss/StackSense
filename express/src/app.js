const express = require('express');
const cors = require('cors');
const v1Router = require('./routes');
const errorHandler = require('./middleware/errorHandler');

/**
 * Configure Express application.
 */
function createApp() {
  const app = express();

  // Core middleware
  app.use(cors());
  app.use(express.json({ limit: '1mb' }));

  // API v1 routes
  app.use('/api/v1', v1Router);

  // 404 handler for unknown routes
  app.use((req, res) => {
    res.status(404).json({
      error: {
        code: 'route_not_found',
        message: `Route not found: ${req.method} ${req.originalUrl}`,
        details: {},
      },
    });
  });

  // Central error handling middleware
  app.use(errorHandler);

  return app;
}

const app = createApp();

module.exports = app;
