import React from "react";
import PageHeader from "@/components/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ProfileSettings from "@/components/settings/ProfileSettings";
import CalendarConnections from "@/components/settings/CalendarConnections";
import { User, Calendar } from "lucide-react";

export default function Settings() {
  return (
    <div data-testid="settings-page" className="w-full space-y-6">
      <PageHeader 
        title="Settings" 
        subtitle="Manage your profile settings and active calendar integrations." 
      />
      
      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="grid w-full grid-cols-2 max-w-[400px] mb-6">
          <TabsTrigger 
            value="profile" 
            className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
          >
            <User className="w-4 h-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger 
            value="calendar" 
            className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
          >
            <Calendar className="w-4 h-4" />
            Calendar Connections
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="profile" className="outline-none">
          <ProfileSettings />
        </TabsContent>
        
        <TabsContent value="calendar" className="outline-none">
          <CalendarConnections />
        </TabsContent>
      </Tabs>
    </div>
  );
}

