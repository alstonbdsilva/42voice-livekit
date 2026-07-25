class TwilioServiceClass {
  async searchNumbers(countryCode: string = "US", type: "Local" | "TollFree" = "Local", areaCode?: string) {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 750));
    
    const prefix = areaCode || (countryCode === "NZ" ? "9" : "855");
    return [
      {
        phone_number: countryCode === "NZ" 
          ? `+64 ${prefix} ${Math.floor(100 + Math.random() * 900)} ${Math.floor(1000 + Math.random() * 9000)}` 
          : `+1 (${prefix}) ${Math.floor(100 + Math.random() * 900)}-${Math.floor(1000 + Math.random() * 9000)}`,
        friendly_name: `Twilio ${type} Line`,
        capabilities: { voice: true, SMS: type === "Local" }
      },
      {
        phone_number: countryCode === "NZ" 
          ? `+64 ${prefix} ${Math.floor(100 + Math.random() * 900)} ${Math.floor(1000 + Math.random() * 9000)}` 
          : `+1 (${prefix}) ${Math.floor(100 + Math.random() * 900)}-${Math.floor(1000 + Math.random() * 9000)}`,
        friendly_name: `Twilio Backup Trunk`,
        capabilities: { voice: true, SMS: true }
      },
      {
        phone_number: countryCode === "NZ" 
          ? `+64 ${prefix} ${Math.floor(100 + Math.random() * 900)} ${Math.floor(1000 + Math.random() * 9000)}` 
          : `+1 (${prefix}) ${Math.floor(100 + Math.random() * 900)}-${Math.floor(1000 + Math.random() * 9000)}`,
        friendly_name: `Campaign Line`,
        capabilities: { voice: true, SMS: false }
      }
    ];
  }

  async buyNumber(phoneNumber: string, friendlyName: string) {
    await new Promise(resolve => setTimeout(resolve, 800));
    return {
      sid: `PN${Math.random().toString(36).substring(2, 17).toUpperCase()}`,
      phone_number: phoneNumber,
      friendly_name: friendlyName,
      capabilities: { voice: true, SMS: true }
    };
  }

  async listNumbers() {
    return [];
  }

  async releaseNumber(sid: string) {
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}

export const TwilioService = new TwilioServiceClass();
export default TwilioService;
