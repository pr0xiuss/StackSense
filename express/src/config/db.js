const mongoose = require('mongoose');

async function connectDB(uri) {
  const mongoUri =  process.env.MONGODB_URI || 'mongodb://localhost:27017/stacksense';

  try {
    const connection = await mongoose.connect(mongoUri, {
      autoIndex: true,
      serverSelectionTimeoutMS: 5000,
    });

    return connection;
  } catch (error) {
    console.error(`MongoDB connection error: ${error.message}`);
    throw error;
  }
}

async function disconnectDB() {
  if (mongoose.connection.readyState !== 0) {
    await mongoose.disconnect();
  }
}

mongoose.connection.on('disconnected', () => {
  if (process.env.NODE_ENV !== 'test') {
    console.log('MongoDB connection disconnected');
  }
});

module.exports = {
  connectDB,
  disconnectDB,
};
