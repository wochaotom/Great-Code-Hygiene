async function callWithRetry(operation, options = {}) {
  const maxAttempts = options.maxAttempts ?? 3;
  let lastError;

  for (let attempt = 0; attempt <= maxAttempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError;
}

module.exports = { callWithRetry };
