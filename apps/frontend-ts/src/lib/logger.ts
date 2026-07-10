/**
 * Simple logging utility for frontend debugging
 * Logs to browser console with consistent formatting
 */

export enum LogLevel {
  DEBUG = "DEBUG",
  INFO = "INFO",
  WARN = "WARN",
  ERROR = "ERROR",
}

const LOG_PREFIX = "[JobRaider]";

export class Logger {
  private context: string;

  constructor(context: string) {
    this.context = context;
  }

  private log(level: LogLevel, message: string, ...args: unknown[]) {
    const timestamp = new Date().toISOString();
    const prefix = `${LOG_PREFIX} [${timestamp}] [${level}] [${this.context}]`;

    switch (level) {
      case LogLevel.DEBUG:
        console.debug(prefix, message, ...args);
        break;
      case LogLevel.INFO:
        console.log(prefix, message, ...args);
        break;
      case LogLevel.WARN:
        console.warn(prefix, message, ...args);
        break;
      case LogLevel.ERROR:
        console.error(prefix, message, ...args);
        break;
    }
  }

  debug(message: string, ...args: unknown[]) {
    this.log(LogLevel.DEBUG, message, ...args);
  }

  info(message: string, ...args: unknown[]) {
    this.log(LogLevel.INFO, message, ...args);
  }

  warn(message: string, ...args: unknown[]) {
    this.log(LogLevel.WARN, message, ...args);
  }

  error(message: string, ...args: unknown[]) {
    this.log(LogLevel.ERROR, message, ...args);
  }

  /**
   * Log API request
   */
  logRequest(method: string, path: string, body?: unknown) {
    this.info(
      `API Request: ${method} ${path}`,
      body ? JSON.stringify(body) : "",
    );
  }

  /**
   * Log API response
   */
  logResponse(status: number, path: string, data?: unknown) {
    const statusColor =
      status >= 200 && status < 300 ? "✅" : status >= 400 ? "❌" : "⚠️";
    this.info(
      `API Response: ${statusColor} ${status} ${path}`,
      data ? JSON.stringify(data).substring(0, 200) : "",
    );
  }

  /**
   * Log API error
   */
  logError(method: string, path: string, error: unknown) {
    this.error(`API Error: ${method} ${path}`, error);
  }
}

/**
 * Create a logger instance for a specific context
 */
export function createLogger(context: string): Logger {
  return new Logger(context);
}
