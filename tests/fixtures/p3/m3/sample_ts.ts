/**
 * Sample TypeScript module for M3 IR normalization fixtures.
 */
import { User, UserRepository } from './types';

export interface AuthenticationResult {
  token: string;
  expiresIn: number;
}

export class AuthService {
  constructor(private readonly repo: UserRepository) {}

  public async authenticate(username: string): Promise<User | null> {
    return this.repo.findByUsername(username);
  }
}

