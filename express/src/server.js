require('dotenv').config();
const app = require('./app');
const { connectDB, disconnectDB } = require('./config/db');

const PORT = process.env.PORT || 5000;

async function startServer() {
  try {
    await connectDB();
    console.log('MongoDB connected successfully');

    const server = app.listen(PORT, () => {
      console.log(`StackSense Express server listening on port ${PORT}`);
    });

    const gracefulShutdown = async (signal) => {
      console.log(`Received ${signal}. Shutting down gracefully...`);
      server.close(async () => {
        try {
          await disconnectDB();
          console.log('MongoDB connection closed. Process terminating.');
          process.exit(0);
        } catch (err) {
          console.error('Error during database disconnection:', err);
          process.exit(1);
        }
      });
    };

    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
    process.on('SIGINT', () => gracefulShutdown('SIGINT'));
  } catch (error) {
    console.error(`Failed to start server: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  startServer();
}

module.exports = { startServer };
