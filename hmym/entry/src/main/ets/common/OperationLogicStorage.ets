import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface OperationLogic {
  id: string;
  inputText: string;
  operationLogic: string;
  createTime: string;
}

export class OperationLogicStorage {
  private static instance: OperationLogicStorage;
  private storage: Map<string, OperationLogic> = new Map();
  private listeners: Set<() => void> = new Set();
  private preferences: preferences.Preferences | null = null;
  private context: common.Context | null = null;
  private readonly STORE_NAME = 'operation_logic_store';

  static getInstance(): OperationLogicStorage {
    if (!OperationLogicStorage.instance) {
      OperationLogicStorage.instance = new OperationLogicStorage();
    }
    return OperationLogicStorage.instance;
  }

  async init(context: common.Context): Promise<void> {
    this.context = context;
    try {
      this.preferences = await preferences.getPreferences(context, this.STORE_NAME);
      await this.loadFromPreferences();
    } catch (error) {
      console.error('Failed to init preferences:', JSON.stringify(error));
    }
  }

  private async loadFromPreferences(): Promise<void> {
    if (!this.preferences) return;

    try {
      const dataStr = await this.preferences.get('operation_logics', '') as string;
      if (dataStr) {
        const logics: OperationLogic[] = JSON.parse(dataStr);
        this.storage.clear();
        logics.forEach(logic => {
          this.storage.set(logic.id, logic);
        });
        this.notifyListeners();
      }
    } catch (error) {
      console.error('Failed to load from preferences:', JSON.stringify(error));
    }
  }

  private async saveToPreferences(): Promise<void> {
    if (!this.preferences) return;

    try {
      const logics = Array.from(this.storage.values());
      const dataStr = JSON.stringify(logics);
      await this.preferences.put('operation_logics', dataStr);
      await this.preferences.flush();
    } catch (error) {
      console.error('Failed to save to preferences:', JSON.stringify(error));
    }
  }

  async addLogic(logic: OperationLogic): Promise<void> {
    this.storage.set(logic.id, logic);
    await this.saveToPreferences();
    this.notifyListeners();
  }

  getAllLogics(): OperationLogic[] {
    return Array.from(this.storage.values()).reverse();
  }

  async removeLogic(id: string): Promise<void> {
    this.storage.delete(id);
    await this.saveToPreferences();
    this.notifyListeners();
  }

  addListener(callback: () => void): void {
    this.listeners.add(callback);
  }

  removeListener(callback: () => void): void {
    this.listeners.delete(callback);
  }

  private notifyListeners(): void {
    this.listeners.forEach(callback => callback());
  }
}
