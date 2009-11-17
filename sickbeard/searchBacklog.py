# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.



import datetime
import sqlite3
import threading
import time
import traceback

from sickbeard import db, exceptions, helpers, nzb, scheduler
from sickbeard.logging import *
from sickbeard.common import *

class BacklogSearchScheduler(scheduler.Scheduler):

    def forceSearch(self):
        self.action._set_lastBacklog(1)
        self.lastRun = datetime.datetime.fromordinal(1)
        

class BacklogSearcher:

    def __init__(self):
        
        self._lastBacklog = self._get_lastBacklog()
        self.cycleTime = 3
        self.lock = threading.Lock()
        self.amActive = False

    def searchBacklog(self):
        
        if self.amActive == True:
            Logger().log("Backlog is still running, not starting it again", DEBUG)
            return
        
        self.amActive = True
        
        self._get_lastBacklog()
        
        curDate = datetime.date.today().toordinal()
        
        if curDate - self._lastBacklog >= self.cycleTime:
            
            epList = self._getBacklogEpisodesToSearchFor()
            
            if epList == None or len(epList) == 0:
                Logger().log("No episodes were found in the backlog")
                self._set_lastBacklog(curDate)
                self.amActive = False
                return
            
            for curEp in epList:
                
                foundNZBs = nzb.findNZB(curEp)
                
                if len(foundNZBs) == 0:
                    Logger().log("Unable to find NZB for " + curEp.prettyName())
                
                else:
                    # just use the first result for now
                    nzb.snatchNZB(foundNZBs[0])
                    
            self._set_lastBacklog(curDate)
            
        self.amActive = False
            
    
    def _get_lastBacklog(self):
    
        myDB = db.DBConnection()
        myDB.checkDB()
        
        sqlResults = []
        
        Logger().log("Retrieving the last check time from the DB", DEBUG)
        
        try:
            sql = "SELECT * FROM info"
            Logger().log("SQL: " + sql, DEBUG)
            sqlResults = myDB.connection.execute(sql).fetchall()
        except sqlite3.DatabaseError as e:
            Logger().log("Fatal error executing query '" + sql + "': " + str(e), ERROR)
            raise
    
        if len(sqlResults) == 0:
            lastBacklog = 1
        elif sqlResults[0]["last_backlog"] == None or sqlResults[0]["last_backlog"] == "":
            lastBacklog = 1
        else:
            lastBacklog = int(sqlResults[0]["last_backlog"])
    
        self._lastBacklog = lastBacklog
        return self._lastBacklog
    
    
    def _set_lastBacklog(self, when):
    
        myDB = db.DBConnection()
        myDB.checkDB()
        
        Logger().log("Setting the last backlog in the DB to " + str(when), DEBUG)
        
        try:
            sql = "UPDATE info SET last_backlog=" + str(when)
            Logger().log("SQL: " + sql, DEBUG)
            myDB.connection.execute(sql)
            myDB.connection.commit()
        except sqlite3.DatabaseError as e:
            Logger().log("Fatal error executing query '" + sql + "': " + str(e), ERROR)
            raise
    
    
    def _getBacklogEpisodesToSearchFor(self):
    
        myDB = db.DBConnection()
        myDB.checkDB()
        
        curDate = datetime.date.today().toordinal()
        sqlResults = []
        
        foundEps = []
        
        Logger().log("Searching the database for a list of backlogged episodes to download")
        
        try:
            sql = "SELECT * FROM tv_episodes WHERE status IN (" + str(BACKLOG) + ", " + str(DISCBACKLOG) + ")"
            Logger().log("SQL: " + sql, DEBUG)
            sqlResults = myDB.connection.execute(sql).fetchall()
            print "found", sqlResults
    
        except sqlite3.DatabaseError as e:
            Logger().log("Fatal error executing query '" + sql + "': " + str(e), ERROR)
            raise
    
        for sqlEp in sqlResults:
            print "FFS the status is " + str(sqlEp["status"])
            
            try:
                show = helpers.findCertainShow (sickbeard.showList, int(sqlEp["showid"]))
            except exceptions.MultipleShowObjectsException:
                Logger().log("ERROR: expected to find a single show matching " + sqlEp["showid"], ERROR) 
                return None
            ep = show.getEpisode(sqlEp["season"], sqlEp["episode"], True)
            foundEps.append(ep)
            Logger().log("Added " + ep.prettyName() + " to the list of episodes to download (status=" + str(ep.status))
        
        return foundEps

    def run(self):
        self.searchBacklog()