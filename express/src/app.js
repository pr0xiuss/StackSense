const express = require('express');
const cors = require('cors');
const v1Router = require('./routes');
const errorHandler = require('./middleware/errorHandler');

function createApp() {
  const app = express();

  app.use(cors());
  app.use(express.json({ limit: '1mb' }));
  app.use('/api/v1', v1Router);
  app.use((req, res) => {
    res.status(404).json({
      error: {
        code: 'route_not_found',
        message: `Route not found: ${req.method} ${req.originalUrl}`,
        details: {},
      },
    });
  });
  app.use(errorHandler);

  return app;
}

const app = createApp();

module.exports = app;
